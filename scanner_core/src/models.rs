/// Internal Rust data types used during scanning.
/// These are plain Rust structs, NOT PyO3 classes.
/// Conversion to PyO3 types happens in lib.rs.

/// A file entry collected during scanning
#[derive(Clone, Debug)]
pub struct FileEntry {
    pub name: String,
    pub path: String,
    pub size: u64,
    pub modified: f64,
    pub extension: String,
    pub parent_path: String,
}

/// A directory entry collected during scanning
#[derive(Clone, Debug)]
pub struct DirEntry {
    pub name: String,
    pub path: String,
    pub size: u64,
    pub file_count: u64,
    pub dir_count: u64,
    pub parent_path: String,
    pub modified: f64,
    /// Children: either file entries or sub-directory entries
    pub children: Vec<ChildEntry>,
}

/// A child of a directory — can be either a file or a sub-directory
#[derive(Clone, Debug)]
#[allow(dead_code)] // File(FileEntry) is consumed on the Python side via PyO3
pub enum ChildEntry {
    File(FileEntry),
    Dir(DirEntry),
}

/// The complete output of a directory scan
#[derive(Debug)]
pub struct ScanOutput {
    pub all_files: Vec<FileEntry>,
    pub all_dirs: Vec<DirEntry>,
    pub total_size: u64,
    pub total_files: u64,
    pub total_dirs: u64,
    pub skipped_count: u64,
    pub scan_duration: f64,
}

/// Errors that can occur during scanning
#[derive(Debug)]
pub enum ScanError {
    NotFound(String),
    NotADirectory(String),
    Io(std::io::Error),
}

impl std::fmt::Display for ScanError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            ScanError::NotFound(p) => write!(f, "Path not found: {}", p),
            ScanError::NotADirectory(p) => write!(f, "Not a directory: {}", p),
            ScanError::Io(e) => write!(f, "IO error: {}", e),
        }
    }
}

impl From<std::io::Error> for ScanError {
    fn from(e: std::io::Error) -> Self {
        ScanError::Io(e)
    }
}
