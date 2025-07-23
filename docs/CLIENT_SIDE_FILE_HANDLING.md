# Client-Side File Handling in Repo Tools

## Overview

Repo Tools has been migrated to use client-side file handling, ensuring that users work with files from their own computers rather than the server's filesystem. This document explains how the new architecture works.

## Key Changes

### Before (Server-Side)
- Files were read from the server's filesystem (e.g., `/media/ssd/developer`)
- Users saw server paths in the UI
- File operations happened on the server
- Limited to files accessible by the server

### After (Client-Side)
- Files are selected from the user's own computer
- Users see their own file paths
- File operations happen in the browser
- Full access to user's local files (with permission)

## Browser Compatibility

### Full Support (File System Access API)
- **Chrome/Edge 86+**: Full native file system access
- Can read directories recursively
- Can write files back (with permission)

### Partial Support (webkitdirectory)
- **Firefox, Safari**: Limited directory selection
- Can read files but with less flexibility
- Falls back to download for file changes

### No Support
- Older browsers: Manual file selection only
- Very limited functionality

## How It Works

### 1. FileSystemManager (base.html)

The core client-side file handling system is implemented in `base.html`:

```javascript
window.FileSystemManager = {
    // Check browser support
    isSupported: function() { ... },
    
    // Select a directory
    selectDirectory: async function() { ... },
    
    // Read file content
    readFileContent: async function(file) { ... },
    
    // Find Git repositories
    findGitRepositories: function(files) { ... }
}
```

### 2. Local Repository Tool

When users click "Select Folder":
1. Browser file picker opens
2. User grants permission to read the directory
3. Files are scanned for Git repositories
4. Repository contents are processed in the browser
5. Formatted content is copied to clipboard

### 3. XML Parser Tool

The XML parser now:
1. Reads repository files from the user's computer
2. Parses XML entirely in the browser
3. Shows preview of changes
4. Downloads changes as a text file (or applies directly with File System Access API)

### 4. GitHub Repository Tool

GitHub repositories still require server-side processing:
1. Repository is cloned to server temporarily
2. Files are processed and sent to client
3. Temporary files are cleaned up
4. No server paths are exposed to the user

## Security Considerations

### Permissions
- Users must explicitly grant permission for each directory
- Browser shows clear permission prompts
- Permissions are temporary and per-session

### Sandboxing
- File access is sandboxed by the browser
- No access outside selected directories
- No system file access

### Privacy
- Files never leave the user's computer (except GitHub clones)
- All processing happens locally in the browser
- No server storage of user files

## API Changes

### Deprecated Endpoints
These endpoints now return client-side instructions:
- `GET /api/paths` → Returns instruction to use FileSystemManager
- `GET /api/repos` → Returns instruction for client-side detection
- `POST /api/parse-xml` → Returns instruction for client-side parsing
- `POST /api/apply-xml` → Returns instruction for client-side application

### Active Endpoints
- `POST /api/copy-to-clipboard` - Formats and copies content
- `POST /api/clear-cache` - Clears GitHub clone temp files
- `POST /api/server-settings` - Manages server configuration

### Socket.IO Events
- `scan_repos` → Now returns client-side instruction
- `xml_parse` → Now returns client-side instruction
- `xml_apply` → Now returns client-side instruction
- `github_clone` → Still active (server-side only)

## Migration Impact

### For Users
- **Better Privacy**: Your files stay on your computer
- **Better Performance**: No network transfer of files
- **More Control**: Direct access to your filesystem
- **Browser Requirement**: Need modern browser with File API support

### For Developers
- Frontend handles all local file operations
- Backend only processes GitHub clones
- No server filesystem access for local files
- Client-side validation and processing

## Troubleshooting

### "Directory selection not supported"
- Update to Chrome, Edge, or another supported browser
- Use the fallback file input method

### "Permission denied"
- Grant permission when browser prompts
- Check browser settings for file access permissions

### "Cannot read files"
- Ensure files are not locked by another program
- Check file permissions on your system

### "Changes not applying"
- Download changes as a file if direct write not supported
- Apply changes manually to your files

## Future Enhancements

1. **Progressive Web App**: Offline file processing
2. **WebAssembly**: Faster file parsing
3. **IndexedDB**: Local file caching
4. **Service Workers**: Background processing

## Technical Details

### File System Access API
```javascript
// Request directory access
const dirHandle = await window.showDirectoryPicker();

// Read files recursively
for await (const entry of dirHandle.values()) {
    if (entry.kind === 'file') {
        const file = await entry.getFile();
        const content = await file.text();
    }
}
```

### Fallback with webkitdirectory
```html
<input type="file" webkitdirectory multiple />
```

### Client-Side Git Detection
```javascript
// Detect .git directories
if (path.includes('/.git/')) {
    const repoPath = path.substring(0, path.indexOf('/.git/'));
    // Repository found at repoPath
}
```

## Conclusion

The migration to client-side file handling makes Repo Tools more secure, private, and user-friendly. Users maintain full control over their files while enjoying the same powerful features for managing repository contexts.