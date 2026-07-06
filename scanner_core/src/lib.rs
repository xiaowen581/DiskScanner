use pyo3::exceptions::{PyFileNotFoundError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyAny;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};

use crate::scanner::scan_directory;

mod models;
mod scanner;

// ═══════════════════════════════════════════════════
//  PyO3 wrapper classes
// ═══════════════════════════════════════════════════

/// Python-visible FileNode — represents a single file
#[pyclass(name = "FileNode", from_py_object)]
#[derive(Clone)]
pub struct PyFileNode {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub size: u64,
    #[pyo3(get)]
    pub modified: f64,
    #[pyo3(get)]
    pub extension: String,
    #[pyo3(get)]
    pub parent_path: String,
}

#[pymethods]
impl PyFileNode {
    #[new]
    #[pyo3(signature = (name, path, size, modified, extension, parent_path = String::new()))]
    fn new(
        name: String,
        path: String,
        size: u64,
        modified: f64,
        extension: String,
        parent_path: String,
    ) -> Self {
        PyFileNode {
            name,
            path,
            size,
            modified,
            extension,
            parent_path,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "FileNode(name='{}', path='{}', size={})",
            self.name, self.path, self.size
        )
    }
}

/// Python-visible DirNode — represents a directory
#[pyclass(name = "DirNode", from_py_object)]
#[derive(Clone)]
pub struct PyDirNode {
    #[pyo3(get)]
    pub name: String,
    #[pyo3(get)]
    pub path: String,
    #[pyo3(get)]
    pub size: u64,
    #[pyo3(get)]
    pub file_count: u64,
    #[pyo3(get)]
    pub dir_count: u64,
    #[pyo3(get)]
    pub parent_path: String,
    #[pyo3(get)]
    pub modified: f64,
    children: Vec<Py<PyAny>>,
}

#[pymethods]
impl PyDirNode {
    #[new]
    #[pyo3(signature = (name, path, size = 0, file_count = 0, dir_count = 0, children = None, parent_path = String::new(), modified = 0.0))]
    fn new(
        name: String,
        path: String,
        size: u64,
        file_count: u64,
        dir_count: u64,
        children: Option<Vec<Py<PyAny>>>,
        parent_path: String,
        modified: f64,
    ) -> Self {
        PyDirNode {
            name,
            path,
            size,
            file_count,
            dir_count,
            parent_path,
            modified,
            children: children.unwrap_or_default(),
        }
    }

    /// Access children list (mixed FileNode and DirNode)
    #[getter]
    fn children(&self) -> Vec<Py<PyAny>> {
        self.children.clone()
    }

    fn __repr__(&self) -> String {
        format!(
            "DirNode(name='{}', path='{}', size={})",
            self.name, self.path, self.size
        )
    }
}

/// Python-visible ScanResult — holds all scan results
#[pyclass(name = "ScanResult")]
pub struct PyScanResult {
    #[pyo3(get, set)]
    pub root: Option<Py<PyDirNode>>,
    #[pyo3(get, set)]
    pub total_size: u64,
    #[pyo3(get, set)]
    pub total_files: u64,
    #[pyo3(get, set)]
    pub total_dirs: u64,
    #[pyo3(get, set)]
    pub scan_duration: f64,
    #[pyo3(get, set)]
    pub all_files: Vec<Py<PyFileNode>>,
    #[pyo3(get, set)]
    pub all_dirs: Vec<Py<PyDirNode>>,
    #[pyo3(get, set)]
    pub skipped_count: u64,
}

#[pymethods]
impl PyScanResult {
    #[new]
    #[pyo3(signature = (root=None, total_size=0, total_files=0, total_dirs=0, scan_duration=0.0, all_files=None, all_dirs=None, skipped_count=0))]
    fn new(
        root: Option<Py<PyDirNode>>,
        total_size: u64,
        total_files: u64,
        total_dirs: u64,
        scan_duration: f64,
        all_files: Option<Vec<Py<PyFileNode>>>,
        all_dirs: Option<Vec<Py<PyDirNode>>>,
        skipped_count: u64,
    ) -> Self {
        PyScanResult {
            root,
            total_size,
            total_files,
            total_dirs,
            scan_duration,
            all_files: all_files.unwrap_or_default(),
            all_dirs: all_dirs.unwrap_or_default(),
            skipped_count,
        }
    }

    fn __repr__(&self) -> String {
        format!(
            "ScanResult(files={}, dirs={}, size={})",
            self.total_files, self.total_dirs, self.total_size
        )
    }
}

/// Python-visible Scanner — the main scanning interface
#[pyclass(name = "Scanner")]
pub struct PyScanner {
    follow_symlinks: bool,
    file_count: Arc<AtomicU64>,
    current_path: Arc<Mutex<String>>,
}

#[pymethods]
impl PyScanner {
    #[new]
    #[pyo3(signature = (follow_symlinks = false))]
    fn new(follow_symlinks: bool) -> Self {
        PyScanner {
            follow_symlinks,
            file_count: Arc::new(AtomicU64::new(0)),
            current_path: Arc::new(Mutex::new(String::new())),
        }
    }

    /// Get current scan progress as (file_count, current_path)
    #[getter]
    fn progress_info(&self) -> (u64, String) {
        let count = self.file_count.load(Ordering::Relaxed);
        let path = self.current_path.lock().unwrap().clone();
        (count, path)
    }

    /// Scan a directory and return ScanResult
    fn scan(&mut self, py: Python<'_>, root_path: &str) -> PyResult<PyScanResult> {
        // Reset progress
        self.file_count.store(0, Ordering::Relaxed);
        *self.current_path.lock().unwrap() = String::new();

        // Validate path before releasing GIL
        let path = std::path::Path::new(root_path);
        if !path.exists() {
            return Err(PyFileNotFoundError::new_err(format!(
                "路径不存在: {}",
                root_path
            )));
        }
        if !path.is_dir() {
            return Err(PyValueError::new_err(format!(
                "指定路径不是目录: {}",
                root_path
            )));
        }

        let progress = Arc::new((AtomicU64::new(0), Mutex::new(String::new())));
        let progress_clone = progress.clone();
        let follow_symlinks = self.follow_symlinks;
        let root_path_owned = root_path.to_string();

        // Release GIL for the actual scan (parallel traversal)
        let scan_result = py.detach(|| {
            scan_directory(&root_path_owned, follow_symlinks, progress_clone)
        });

        // Update progress from scan
        self.file_count
            .store(progress.0.load(Ordering::Relaxed), Ordering::Relaxed);
        {
            let mut cp = self.current_path.lock().unwrap();
            *cp = progress.1.lock().unwrap().clone();
        }

        let output = scan_result.map_err(|e| match e {
            crate::models::ScanError::NotFound(p) => {
                PyFileNotFoundError::new_err(format!("路径不存在: {}", p))
            }
            crate::models::ScanError::NotADirectory(p) => {
                PyValueError::new_err(format!("指定路径不是目录: {}", p))
            }
            crate::models::ScanError::Io(e) => {
                PyValueError::new_err(format!("IO error: {}", e))
            }
        })?;

        // Convert Rust types to PyO3 types (needs GIL — we have it here)
        self.build_scan_result(py, output)
    }
}

impl PyScanner {
    /// Convert ScanOutput → PyScanResult
    fn build_scan_result(
        &self,
        py: Python<'_>,
        output: crate::models::ScanOutput,
    ) -> PyResult<PyScanResult> {
        // Convert all files to Py<PyFileNode>
        let py_all_files: Vec<Py<PyFileNode>> = output
            .all_files
            .iter()
            .map(|f| {
                Py::new(
                    py,
                    PyFileNode {
                        name: f.name.clone(),
                        path: f.path.clone(),
                        size: f.size,
                        modified: f.modified,
                        extension: f.extension.clone(),
                        parent_path: f.parent_path.clone(),
                    },
                )
            })
            .collect::<Result<Vec<_>, _>>()?;

        // Build parent→children mapping for files
        let mut file_children_map: std::collections::HashMap<String, Vec<Py<PyAny>>> =
            std::collections::HashMap::new();

        for py_file in &py_all_files {
            let parent = py_file.borrow(py).parent_path.clone();
            let obj: Py<PyAny> = py_file.clone_ref(py).into();
            file_children_map.entry(parent).or_default().push(obj);
        }

        // Convert all dirs to Py<PyDirNode>
        let mut py_dirs: Vec<Py<PyDirNode>> = Vec::new();
        let mut dir_path_to_idx: std::collections::HashMap<String, usize> =
            std::collections::HashMap::new();

        for (i, d) in output.all_dirs.iter().enumerate() {
            let py_dir = Py::new(
                py,
                PyDirNode {
                    name: d.name.clone(),
                    path: d.path.clone(),
                    size: d.size,
                    file_count: d.file_count,
                    dir_count: d.dir_count,
                    parent_path: d.parent_path.clone(),
                    modified: d.modified,
                    children: Vec::new(),
                },
            )?;
            dir_path_to_idx.insert(d.path.clone(), i);
            py_dirs.push(py_dir);
        }

        // Populate children for each directory
        for (i, d) in output.all_dirs.iter().enumerate() {
            let mut children: Vec<Py<PyAny>> = Vec::new();

            // Add sub-directory children
            for other_d in &output.all_dirs {
                if other_d.parent_path == d.path {
                    if let Some(&idx) = dir_path_to_idx.get(&other_d.path) {
                        let obj: Py<PyAny> = py_dirs[idx].clone_ref(py).into();
                        children.push(obj);
                    }
                }
            }

            // Add file children
            if let Some(file_objs) = file_children_map.get(&d.path) {
                for obj in file_objs {
                    children.push(obj.clone_ref(py));
                }
            }

            py_dirs[i].borrow_mut(py).children = children;
        }

        // Find root (dir with empty parent_path)
        let root_py = output
            .all_dirs
            .iter()
            .find(|d| d.parent_path.is_empty())
            .and_then(|r| dir_path_to_idx.get(&r.path))
            .map(|&idx| py_dirs[idx].clone_ref(py));

        Ok(PyScanResult {
            root: root_py,
            total_size: output.total_size,
            total_files: output.total_files,
            total_dirs: output.total_dirs,
            scan_duration: output.scan_duration,
            all_files: py_all_files,
            all_dirs: py_dirs,
            skipped_count: output.skipped_count,
        })
    }
}

// ═══════════════════════════════════════════════════
//  Module definition
// ═══════════════════════════════════════════════════

#[pymodule]
fn scanner_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyFileNode>()?;
    m.add_class::<PyDirNode>()?;
    m.add_class::<PyScanResult>()?;
    m.add_class::<PyScanner>()?;
    Ok(())
}
