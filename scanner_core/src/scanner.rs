use std::collections::HashMap;
use std::path::Path;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Instant;

use jwalk::WalkDir;

use crate::models::*;

/// Strip Windows \\?\ long-path prefix for compatibility with Python os.path
fn strip_prefix(s: &str) -> String {
    s.strip_prefix(r"\\?\").unwrap_or(s).to_string()
}

/// Scan a directory tree and return structured results.
///
/// Uses `jwalk` for parallel directory traversal.
/// The scan is done in two phases:
/// 1. Walk the tree and collect all file/directory metadata
/// 2. Build the directory tree bottom-up, computing sizes and counts
pub fn scan_directory(
    root: &str,
    follow_symlinks: bool,
    progress: Arc<(AtomicU64, Mutex<String>)>,
) -> Result<ScanOutput, ScanError> {
    let start = Instant::now();
    let root_path = Path::new(root);

    // Validate path
    if !root_path.exists() {
        return Err(ScanError::NotFound(root.to_string()));
    }
    if !root_path.is_dir() {
        return Err(ScanError::NotADirectory(root.to_string()));
    }

    let root_abs = std::fs::canonicalize(root_path)
        .map_err(|e| ScanError::Io(e))?;
    // Strip Windows \\?\ prefix for compatibility with Python's os.path.abspath
    let root_str = root_abs.to_string_lossy().to_string();
    let root_str = strip_prefix(&root_str);

    // Phase 1: Parallel walk — collect all entries
    let skipped = Arc::new(AtomicU64::new(0));

    let walker = WalkDir::new(&root_abs)
        .follow_links(follow_symlinks)
        .parallelism(jwalk::Parallelism::RayonDefaultPool {
            busy_timeout: std::time::Duration::from_millis(100),
        });

    // Temporary storage for raw directory metadata
    struct RawDirMeta {
        name: String,
        modified: f64,
        parent_path: String,
    }

    let mut files: Vec<FileEntry> = Vec::new();
    let mut dir_meta: HashMap<String, RawDirMeta> = HashMap::new();
    // Track which dirs are children of which parent
    let mut dir_children_map: HashMap<String, Vec<String>> = HashMap::new();

    for entry in walker {
        match entry {
            Ok(entry) => {
                let ft = entry.file_type();
                let path_buf = entry.path();
                let path_str = strip_prefix(&path_buf.to_string_lossy());

                // Update progress
                progress.1.lock().unwrap().clone_from(&path_str);

                if ft.is_dir() {
                    let name = path_buf
                        .file_name()
                        .map(|n| n.to_string_lossy().to_string())
                        .unwrap_or_else(|| path_str.clone());

                    let modified = entry
                        .metadata()
                        .ok()
                        .and_then(|m| m.modified().ok())
                        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                        .map(|d| d.as_secs_f64())
                        .unwrap_or(0.0);

                    let parent_path = if path_buf == root_abs {
                        String::new()
                    } else {
                        strip_prefix(
                            &path_buf
                                .parent()
                                .map(|p| p.to_string_lossy().to_string())
                                .unwrap_or_default(),
                        )
                    };

                    // Track parent→child relationship
                    if !parent_path.is_empty() {
                        dir_children_map
                            .entry(parent_path.clone())
                            .or_default()
                            .push(path_str.clone());
                    }

                    dir_meta.insert(
                        path_str,
                        RawDirMeta {
                            name,
                            modified,
                            parent_path,
                        },
                    );
                } else if ft.is_file() {
                    let metadata = match entry.metadata() {
                        Ok(m) => m,
                        Err(_) => {
                            skipped.fetch_add(1, Ordering::Relaxed);
                            continue;
                        }
                    };

                    let name = path_buf
                        .file_name()
                        .map(|n| n.to_string_lossy().to_string())
                        .unwrap_or_default();

                    let extension = path_buf
                        .extension()
                        .map(|e| format!(".{}", e.to_string_lossy().to_lowercase()))
                        .unwrap_or_default();

                    let parent_path = strip_prefix(
                        &path_buf
                            .parent()
                            .map(|p| p.to_string_lossy().to_string())
                            .unwrap_or_default(),
                    );

                    let size = metadata.len();
                    let modified = metadata
                        .modified()
                        .ok()
                        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
                        .map(|d| d.as_secs_f64())
                        .unwrap_or(0.0);

                    files.push(FileEntry {
                        name,
                        path: path_str,
                        size,
                        modified,
                        extension,
                        parent_path,
                    });

                    progress.0.fetch_add(1, Ordering::Relaxed);
                }
            }
            Err(_) => {
                skipped.fetch_add(1, Ordering::Relaxed);
            }
        }
    }

    // Phase 2: Build directory tree bottom-up (deepest first)
    // Sort directory paths by depth descending so children are processed before parents
    let mut dir_paths: Vec<String> = dir_meta.keys().cloned().collect();
    dir_paths.sort_by(|a, b| {
        let da = a.matches(std::path::MAIN_SEPARATOR).count();
        let db = b.matches(std::path::MAIN_SEPARATOR).count();
        db.cmp(&da)
    });

    let mut dir_nodes: HashMap<String, DirEntry> = HashMap::new();

    for dir_path in &dir_paths {
        let meta = dir_meta.get(dir_path).unwrap();

        // Collect file children for this directory
        let file_children: Vec<FileEntry> = files
            .iter()
            .filter(|f| f.parent_path == *dir_path)
            .cloned()
            .collect();

        let file_count = file_children.len() as u64;
        let file_size: u64 = file_children.iter().map(|f| f.size).sum();

        // Collect sub-directory children (already built, deepest-first)
        let mut sub_dirs: Vec<DirEntry> = Vec::new();
        if let Some(child_dir_paths) = dir_children_map.get(dir_path) {
            for child_path in child_dir_paths {
                if let Some(child) = dir_nodes.remove(child_path) {
                    sub_dirs.push(child);
                }
            }
        }

        let dir_count = sub_dirs.len() as u64;
        let sub_size: u64 = sub_dirs.iter().map(|d| d.size).sum();

        // Build children list: dirs first, then files (matching Python Scanner order)
        let mut children: Vec<ChildEntry> = Vec::new();
        for d in sub_dirs {
            children.push(ChildEntry::Dir(d));
        }
        for f in file_children {
            children.push(ChildEntry::File(f));
        }

        dir_nodes.insert(
            dir_path.clone(),
            DirEntry {
                name: meta.name.clone(),
                path: dir_path.clone(),
                size: file_size + sub_size,
                file_count,
                dir_count,
                parent_path: meta.parent_path.clone(),
                modified: meta.modified,
                children,
            },
        );
    }

    // Build flat all_dirs list
    let mut all_dirs: Vec<DirEntry> = Vec::new();
    // Re-traverse in a BFS order to get the right listing order
    let mut queue = vec![root_str.clone()];
    while let Some(current) = queue.pop() {
        if let Some(_dir) = dir_nodes.get(&current) {
            // Add sub-dir paths to queue for BFS traversal
            if let Some(child_paths) = dir_children_map.get(&current) {
                for cp in child_paths {
                    queue.push(cp.clone());
                }
            }
        }
    }

    // Collect all dirs in order (root first, then BFS)
    // We need to rebuild since we consumed dir_nodes above
    // Let's use a different approach: collect all from the original dir_meta order
    // Actually, let's just collect all remaining dir_nodes
    // First, let's get the root back
    let root_dir = dir_nodes.remove(&root_str);

    // Collect all_dirs by doing BFS on the root tree
    if let Some(ref root) = root_dir {
        collect_dirs_bfs(root, &mut all_dirs);
    }

    let scan_duration = start.elapsed().as_secs_f64();
    let total_size = root_dir.as_ref().map(|r| r.size).unwrap_or(0);
    let total_files = files.len() as u64;
    let total_dirs = all_dirs.len() as u64;
    let skipped_count = skipped.load(Ordering::Relaxed);

    Ok(ScanOutput {
        all_files: files,
        all_dirs,
        total_size,
        total_files,
        total_dirs,
        skipped_count,
        scan_duration,
    })
}

/// Collect all directories via BFS traversal of the directory tree
fn collect_dirs_bfs(dir: &DirEntry, result: &mut Vec<DirEntry>) {
    // Create a shallow copy of this dir (without children to avoid deep clone)
    result.push(DirEntry {
        name: dir.name.clone(),
        path: dir.path.clone(),
        size: dir.size,
        file_count: dir.file_count,
        dir_count: dir.dir_count,
        parent_path: dir.parent_path.clone(),
        modified: dir.modified,
        children: Vec::new(), // Will be populated by PyO3 layer
    });

    // Recurse into sub-directories
    for child in &dir.children {
        if let ChildEntry::Dir(sub_dir) = child {
            collect_dirs_bfs(sub_dir, result);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::io::Write;

    fn create_test_dir() -> tempfile::TempDir {
        let tmpdir = tempfile::tempdir().expect("Failed to create temp dir");

        // Create files
        write_file(tmpdir.path().join("file1.txt"), 1000);
        write_file(tmpdir.path().join("file2.py"), 2000);

        // Create subdirectory with file
        let subdir = tmpdir.path().join("subdir");
        fs::create_dir(&subdir).unwrap();
        write_file(subdir.join("file3.mp4"), 5000);

        // Create empty subdirectory
        fs::create_dir(tmpdir.path().join("empty")).unwrap();

        // Create deep nesting: a/b/c/deep.txt
        let deep = tmpdir.path().join("a").join("b").join("c");
        fs::create_dir_all(&deep).unwrap();
        write_file(deep.join("deep.txt"), 300);

        tmpdir
    }

    fn write_file(path: impl AsRef<Path>, size: usize) {
        let path = path.as_ref();
        if let Some(parent) = path.parent() {
            fs::create_dir_all(parent).ok();
        }
        let mut f = fs::File::create(path).unwrap();
        f.write_all(&vec![0u8; size]).unwrap();
    }

    fn make_progress() -> Arc<(AtomicU64, Mutex<String>)> {
        Arc::new((AtomicU64::new(0), Mutex::new(String::new())))
    }

    #[test]
    fn test_scan_basic() {
        let tmpdir = create_test_dir();
        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();

        assert_eq!(result.total_files, 4); // file1, file2, file3, deep
        assert!(result.total_dirs >= 4); // root, subdir, empty, a, a/b, a/b/c
        assert_eq!(result.skipped_count, 0);
        assert!(result.scan_duration >= 0.0);
    }

    #[test]
    fn test_scan_total_size() {
        let tmpdir = create_test_dir();
        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();

        // 1000 + 2000 + 5000 + 300 = 8300
        assert_eq!(result.total_size, 8300);
    }

    #[test]
    fn test_scan_all_files() {
        let tmpdir = create_test_dir();
        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();

        let mut names: Vec<&str> = result.all_files.iter().map(|f| f.name.as_str()).collect();
        names.sort();
        assert_eq!(names, vec!["deep.txt", "file1.txt", "file2.py", "file3.mp4"]);
    }

    #[test]
    fn test_scan_empty_dir() {
        let tmpdir = tempfile::tempdir().unwrap();
        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();

        assert_eq!(result.total_files, 0);
        assert_eq!(result.total_size, 0);
        assert!(result.total_dirs >= 1);
    }

    #[test]
    fn test_scan_dir_size_accumulation() {
        let tmpdir = create_test_dir();
        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();

        // Find "subdir" — should have size 5000
        let subdir = result
            .all_dirs
            .iter()
            .find(|d| d.name == "subdir")
            .expect("subdir not found");
        assert_eq!(subdir.size, 5000);
        assert_eq!(subdir.file_count, 1);

        // Find "c" dir — should have size 300
        let c_dir = result
            .all_dirs
            .iter()
            .find(|d| d.name == "c")
            .expect("dir 'c' not found");
        assert_eq!(c_dir.size, 300);
    }

    #[test]
    fn test_scan_file_extensions() {
        let tmpdir = create_test_dir();
        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();

        let exts: Vec<&str> = result.all_files.iter().map(|f| f.extension.as_str()).collect();
        assert!(exts.contains(&".txt"));
        assert!(exts.contains(&".py"));
        assert!(exts.contains(&".mp4"));
    }

    #[test]
    fn test_scan_nonexistent_path() {
        let result = scan_directory("/nonexistent/path/xyz", false, make_progress());
        assert!(result.is_err());
        match result.unwrap_err() {
            ScanError::NotFound(_) => {}
            other => panic!("Expected NotFound, got: {:?}", other),
        }
    }

    #[test]
    fn test_scan_file_as_path() {
        let tmpdir = create_test_dir();
        let file_path = tmpdir.path().join("file1.txt");
        let result = scan_directory(file_path.to_str().unwrap(), false, make_progress());
        assert!(result.is_err());
        match result.unwrap_err() {
            ScanError::NotADirectory(_) => {}
            other => panic!("Expected NotADirectory, got: {:?}", other),
        }
    }

    #[test]
    fn test_scan_many_files() {
        let tmpdir = tempfile::tempdir().unwrap();
        for i in 0..200 {
            let path = tmpdir.path().join(format!("file_{:04}.dat", i));
            write_file(&path, 100 + i);
        }

        let start = Instant::now();
        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();
        let elapsed = start.elapsed();

        assert_eq!(result.total_files, 200);
        assert!(elapsed.as_secs_f64() < 5.0, "Scan took too long: {:?}", elapsed);
    }

    #[test]
    fn test_scan_subdirectory_sizes() {
        let tmpdir = tempfile::tempdir().unwrap();
        let sub2 = tmpdir.path().join("sub1").join("sub2");
        fs::create_dir_all(&sub2).unwrap();
        write_file(sub2.join("file.bin"), 10000);

        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();

        let sub1 = result
            .all_dirs
            .iter()
            .find(|d| d.name == "sub1")
            .expect("sub1 not found");
        assert_eq!(sub1.size, 10000);

        let sub2_node = result
            .all_dirs
            .iter()
            .find(|d| d.name == "sub2")
            .expect("sub2 not found");
        assert_eq!(sub2_node.size, 10000);
    }

    #[test]
    fn test_scan_mixed_extensions() {
        let tmpdir = tempfile::tempdir().unwrap();
        for ext in &[".txt", ".py", ".js", ".mp4", ""] {
            let name = if ext.is_empty() {
                "noext".to_string()
            } else {
                format!("test{}", ext)
            };
            write_file(tmpdir.path().join(&name), 500);
        }

        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();

        let exts: Vec<&str> = result.all_files.iter().map(|f| f.extension.as_str()).collect();
        assert!(exts.contains(&".txt"));
        assert!(exts.contains(&".py"));
        assert!(exts.contains(&".js"));
        assert!(exts.contains(&".mp4"));
        assert!(exts.contains(&"")); // no extension
    }

    #[test]
    fn test_scan_dir_file_and_subdir_count() {
        let tmpdir = tempfile::tempdir().unwrap();
        write_file(tmpdir.path().join("a.txt"), 100);
        write_file(tmpdir.path().join("b.txt"), 200);
        fs::create_dir(tmpdir.path().join("sub")).unwrap();
        write_file(tmpdir.path().join("sub").join("c.txt"), 300);

        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();

        // Root dir should have 2 files and 1 subdir
        let root = result
            .all_dirs
            .iter()
            .find(|d| d.parent_path.is_empty())
            .expect("root not found");
        assert_eq!(root.file_count, 2);
        assert_eq!(root.dir_count, 1);
    }

    #[test]
    fn test_scan_reuse() {
        let tmpdir = create_test_dir();
        let r1 =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();
        let r2 =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();
        assert_eq!(r1.total_files, r2.total_files);
        assert_eq!(r1.total_size, r2.total_size);
    }

    #[test]
    fn test_scan_deep_nesting() {
        let tmpdir = create_test_dir();
        let result =
            scan_directory(tmpdir.path().to_str().unwrap(), false, make_progress()).unwrap();

        let deep_file = result
            .all_files
            .iter()
            .find(|f| f.name == "deep.txt")
            .expect("deep.txt not found");
        assert_eq!(deep_file.size, 300);
        assert!(deep_file.parent_path.contains("c"));
    }
}
