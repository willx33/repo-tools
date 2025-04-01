import os
import re
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple
import xml.etree.ElementTree as ET
from xml.dom import minidom
import difflib
import html

# Set up logging with more verbose output for debugging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class XMLParserError(Exception):
    """Exception raised for errors in the XML parser."""
    pass

class FileChange:
    """Class representing a file change from parsed XML."""
    
    def __init__(
        self, 
        operation: str, 
        path: str, 
        code: Optional[str] = None,
        search: Optional[str] = None,
        summary: Optional[str] = None
    ):
        """Initialize a FileChange object.
        
        Args:
            operation: The operation type (CREATE, UPDATE, DELETE, MODIFY)
            path: The file path relative to the repository root
            code: The file content (for CREATE and UPDATE operations) or replacement code (for MODIFY)
            search: The search pattern to locate content to replace (for MODIFY operations)
            summary: A summary of the changes (optional)
        """
        self.operation = operation.upper()
        self.path = path
        self.code = code
        self.search = search
        self.summary = summary
    
    def __repr__(self) -> str:
        """Return a string representation of the FileChange object."""
        return f"FileChange({self.operation}, {self.path})"

def extract_xml_from_markdown(text: str) -> str:
    """Extract XML content from markdown code blocks if present.
    
    Args:
        text: The text that may contain markdown-formatted XML
        
    Returns:
        The extracted XML content or the original text if no code blocks found
    """
    # Look for markdown code blocks (```xml ... ```)
    code_block_pattern = r"```(?:xml)?\s*\n(.*?)```"
    match = re.search(code_block_pattern, text, re.DOTALL)
    
    if match:
        # Extract content inside the code block
        xml_content = match.group(1)
        return xml_content
    
    # Return the original text if no patterns matched
    return text

def extract_content_between_delimiters(text: str) -> str:
    """Extract content between === delimiters with improved robustness.
    
    This function now handles variations in how delimiters are formatted,
    including extra whitespace and inconsistent indentation.
    
    Args:
        text: The text that may contain content between === delimiters
        
    Returns:
        The content between the delimiters or the original text if no delimiters found
    """
    # Handle empty or None input
    if not text:
        return text
        
    # Handle case where text is just delimiters
    if text.strip() == "===":
        return ""
        
    lines = text.split('\n')
    
    # Try to find start and end delimiter lines
    start_idx = -1
    end_idx = -1
    
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        if stripped_line == "===" and start_idx == -1:
            start_idx = i
        elif stripped_line == "===" and start_idx != -1:
            end_idx = i
            break
    
    # If we found both delimiters, extract the content between them
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        content = '\n'.join(lines[start_idx + 1:end_idx])
        # Remove any trailing whitespace from the content
        return content.rstrip()
    
    # Additional check: sometimes delimiters might be on the same line as content
    delimiter_pattern = r"===\s*\n(.*?)\n\s*==="
    match = re.search(delimiter_pattern, text, re.DOTALL)
    if match:
        return match.group(1).rstrip()
    
    # If we didn't find delimiters, return the original text
    return text

def normalize_whitespace(text: str, preserve_structure: bool = False) -> str:
    """Normalize whitespace in a text string.
    
    Args:
        text: The text to normalize
        preserve_structure: If True, preserve newlines but normalize other whitespace
        
    Returns:
        The normalized text
    """
    if not preserve_structure:
        # Replace all whitespace sequences with a single space
        normalized = re.sub(r'\s+', ' ', text)
        # Trim leading and trailing whitespace
        normalized = normalized.strip()
        return normalized
    
    # Preserve structure but normalize indentation and other whitespace
    lines = []
    for line in text.splitlines():
        # Trim each line and normalize internal whitespace
        trimmed = re.sub(r'\s+', ' ', line.strip())
        lines.append(trimmed)
    
    # Join with newlines to preserve structure
    return '\n'.join(lines)

def normalize_line_endings(text: str) -> str:
    """Normalize line endings to LF (Unix style)."""
    # Replace Windows line endings (CRLF) with Unix line endings (LF)
    return text.replace('\r\n', '\n')

def parse_xml_string(xml_string: str) -> List[FileChange]:
    """Parse an XML string into a list of FileChange objects.
    
    Supports multiple XML formats:
    1. <changed_files><file><file_operation>...</file></changed_files>
    2. <code_changes><file path="..." action="..."><change>...</change></file></code_changes>
    
    Args:
        xml_string: The XML string to parse
        
    Returns:
        A list of FileChange objects representing the changes
        
    Raises:
        XMLParserError: If the XML string is invalid or cannot be parsed
    """
    try:
        # Try to extract XML content from code blocks if necessary
        xml_string = extract_xml_from_markdown(xml_string)
        
        # Clean up the XML string
        xml_string = xml_string.strip()
        
        # Handle empty or whitespace-only input
        if not xml_string:
            raise XMLParserError("Empty XML string provided")
        
        # Detect which format we're dealing with
        if "<code_changes>" in xml_string:
            return parse_code_changes_format(xml_string)
        elif "<changed_files>" in xml_string:
            return parse_changed_files_format(xml_string)
        else:
            raise XMLParserError("Unknown XML format. Expected either <code_changes> or <changed_files>")
            
    except Exception as e:
        logger.error(f"Error in parse_xml_string: {str(e)}")
        raise XMLParserError(f"Failed to parse XML: {str(e)}")

def parse_changed_files_format(xml_string: str) -> List[FileChange]:
    """Parse the original <changed_files> format."""
    try:
        # First escape any HTML content in the XML
        def escape_html_content(match):
            tag_name = match.group(1)
            content = match.group(2)
            # Log the content length for debugging
            logger.debug(f"Escaping content in {tag_name} tag, length: {len(content)}")
            # Escape special XML characters
            content = content.replace('&', '&amp;')
            content = content.replace('<', '&lt;')
            content = content.replace('>', '&gt;')
            content = content.replace('"', '&quot;')
            content = content.replace("'", '&apos;')
            return f"<{tag_name}>{content}</{tag_name}>"

        # Escape HTML content in file_search and file_code tags
        # Use a more precise pattern that handles multiline content
        xml_string = re.sub(
            r'<(file_search|file_code)>\s*(.*?)\s*</\1>',
            escape_html_content,
            xml_string,
            flags=re.DOTALL
        )
        
        # Log the number of matches found
        matches = re.findall(r'<(file_search|file_code)>\s*(.*?)\s*</\1>', xml_string, re.DOTALL)
        logger.debug(f"Found {len(matches)} HTML content blocks to escape")
        
        # Use minidom for parsing
        dom = minidom.parseString(xml_string)
        
        # Find the changed_files node
        changed_files_nodes = dom.getElementsByTagName("changed_files")
        if not changed_files_nodes:
            raise XMLParserError("No 'changed_files' element found in XML")
        
        changed_files_node = changed_files_nodes[0]
        
        # Extract file nodes
        file_nodes = changed_files_node.getElementsByTagName("file")
        if not file_nodes:
            raise XMLParserError("No 'file' elements found in XML")
            
        logger.debug(f"Found {len(file_nodes)} file nodes to process")
        
        # Parse each file node
        changes = []
        for file_node in file_nodes:
            # Extract file operation
            operation_nodes = file_node.getElementsByTagName("file_operation")
            if not operation_nodes:
                logger.warning("No 'file_operation' element found in file node, skipping")
                continue
            operation = operation_nodes[0].firstChild.nodeValue.strip()
            
            # Extract file path
            path_nodes = file_node.getElementsByTagName("file_path")
            if not path_nodes:
                logger.warning("No 'file_path' element found in file node, skipping")
                continue
            path = path_nodes[0].firstChild.nodeValue.strip()
            
            # Log the operation and path for debugging
            logger.debug(f"Processing file: {path} with operation: {operation}")
            
            # Extract file content (if available)
            code = None
            code_nodes = file_node.getElementsByTagName("file_code")
            if code_nodes and code_nodes[0].firstChild:
                code = code_nodes[0].firstChild.nodeValue
                logger.debug(f"Found code content, length: {len(code)}")
            
            search = None
            search_nodes = file_node.getElementsByTagName("file_search")
            if search_nodes and search_nodes[0].firstChild:
                search = search_nodes[0].firstChild.nodeValue
                logger.debug(f"Found search content, length: {len(search)}")

                if operation.upper() in ["CREATE", "UPDATE"] and search:
                    operation = "MODIFY"
                    logger.debug(f"Operation changed to MODIFY due to search pattern")

            summary = None
            summary_nodes = file_node.getElementsByTagName("file_summary")
            if summary_nodes and summary_nodes[0].firstChild:
                summary = summary_nodes[0].firstChild.nodeValue.strip()
                logger.debug(f"Found summary: {summary}")
            
            # Create FileChange object
            change = FileChange(operation, path, code, search, summary)
            changes.append(change)
            logger.debug(f"Successfully created FileChange object for {path}")
        
        logger.info(f"Successfully processed {len(changes)} file changes")
        return changes
    
    except Exception as e:
        logger.error(f"Error parsing changed_files format XML: {str(e)}")
        raise XMLParserError(f"Failed to parse XML: {str(e)}")

def parse_code_changes_format(xml_string: str) -> List[FileChange]:
    """Parse the new <code_changes> format with search/content delimiters."""
    changes = []
    
    try:
        # Extract all file elements with various attribute formats
        # First try double quotes
        file_pattern = r"<file\s+path=\"(.*?)\"\s+action=\"(.*?)\">(.*?)</file>"
        file_matches = re.findall(file_pattern, xml_string, re.DOTALL)
        
        if not file_matches:
            # Try with single quotes
            file_pattern = r"<file\s+path='(.*?)'\s+action='(.*?)'>(.*?)</file>"
            file_matches = re.findall(file_pattern, xml_string, re.DOTALL)
        
        if not file_matches:
            # Try with attributes in different order
            file_pattern = r"<file\s+action=\"(.*?)\"\s+path=\"(.*?)\">(.*?)</file>"
            matches = re.findall(file_pattern, xml_string, re.DOTALL)
            if matches:
                # Reorder to match our expected format
                file_matches = [(path, action, content) for action, path, content in matches]
        
        if not file_matches:
            # Try with attributes in different order and single quotes
            file_pattern = r"<file\s+action='(.*?)'\s+path='(.*?)'>(.*?)</file>"
            matches = re.findall(file_pattern, xml_string, re.DOTALL)
            if matches:
                # Reorder to match our expected format
                file_matches = [(path, action, content) for action, path, content in matches]
        
        if not file_matches:
            # Try without quotes
            file_pattern = r"<file\s+path=([^\s>]*)\s+action=([^\s>]*)>(.*?)</file>"
            file_matches = re.findall(file_pattern, xml_string, re.DOTALL)
        
        # If still no matches, try a more lenient pattern
        if not file_matches:
            # This pattern is more flexible with whitespace and attribute order
            file_pattern = r"<file\s+(?:path\s*=\s*[\"']?(.*?)[\"']?\s+action\s*=\s*[\"']?(.*?)[\"']?|action\s*=\s*[\"']?(.*?)[\"']?\s+path\s*=\s*[\"']?(.*?)[\"']?)>(.*?)</file>"
            matches = re.findall(file_pattern, xml_string, re.DOTALL)
            if matches:
                file_matches = []
                for match in matches:
                    if match[0] and match[1]:  # path first, then action
                        file_matches.append((match[0], match[1], match[4]))
                    else:  # action first, then path
                        file_matches.append((match[3], match[2], match[4]))
        
        if not file_matches:
            raise XMLParserError("No valid file elements found in XML")
        
        # Process the matches
        for path, action, file_content in file_matches:
            try:
                # Clean up the path and action
                path = path.strip()
                action = action.strip().upper()
                
                # Validate path and action
                if not path:
                    logger.warning("Empty file path found, skipping")
                    continue
                    
                if action not in ["CREATE", "UPDATE", "DELETE", "MODIFY", "REWRITE"]:
                    logger.warning(f"Invalid action '{action}' found, skipping")
                    continue
                
                # Extract all change elements within this file
                change_pattern = r"<change>(.*?)</change>"
                change_matches = re.findall(change_pattern, file_content, re.DOTALL)
                
                for change_content in change_matches:
                    try:
                        # Extract description, search, and content sections
                        description = None
                        description_match = re.search(r"<description>(.*?)</description>", change_content, re.DOTALL)
                        if description_match:
                            description = description_match.group(1).strip()
                        
                        search = None
                        search_match = re.search(r"<search>(.*?)</search>", change_content, re.DOTALL)
                        if search_match:
                            search_text = search_match.group(1)
                            search = extract_content_between_delimiters(search_text)
                        
                        content = None
                        content_match = re.search(r"<content>(.*?)</content>", change_content, re.DOTALL)
                        if content_match:
                            content_text = content_match.group(1)
                            content = extract_content_between_delimiters(content_text)
                        
                        # Map actions to operations
                        operation = action
                        if operation == "REWRITE":
                            operation = "UPDATE"
                        
                        # Create the FileChange object
                        change = FileChange(operation, path, content, search, description)
                        changes.append(change)
                        
                    except Exception as e:
                        logger.error(f"Error processing change element: {str(e)}")
                        continue
                    
                # If no change blocks were found, treat the entire file content as a single change
                if not change_matches:
                    try:
                        operation = action
                        if operation == "REWRITE":
                            operation = "UPDATE"
                        
                        change = FileChange(operation, path, file_content.strip())
                        changes.append(change)
                    except Exception as e:
                        logger.error(f"Error processing file content: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.error(f"Error processing file element: {str(e)}")
                continue
        
        if not changes:
            raise XMLParserError("No valid changes found in XML")
            
        # Log the detected changes for debugging
        for change in changes:
            logger.debug(f"Detected change: {change.operation} for {change.path}")
            if change.search:
                logger.debug(f"Search pattern length: {len(change.search)} characters")
            if change.code:
                logger.debug(f"Content length: {len(change.code)} characters")
        
        return changes
        
    except Exception as e:
        logger.error(f"Error parsing code_changes format XML: {str(e)}")
        raise XMLParserError(f"Failed to parse XML: {str(e)}")

def find_closest_match(search_pattern: str, file_content: str) -> Tuple[Optional[str], float]:
    """Find the closest match for a search pattern in a file.
    
    This function uses difflib to find the closest matching block in the file
    content that resembles the search pattern. This helps handle cases where
    there are minor differences in whitespace or formatting.
    
    Args:
        search_pattern: The search pattern to look for
        file_content: The content of the file to search in
        
    Returns:
        Tuple of (closest matching text if found, similarity ratio)
    """
    # First try to find an exact match (handles the most common case quickly)
    if search_pattern in file_content:
        return search_pattern, 1.0
    
    # Normalize line endings in both search pattern and file content
    search_pattern = normalize_line_endings(search_pattern)
    file_content = normalize_line_endings(file_content)
    
    # Try with normalized search pattern (preserving structure)
    normalized_search = normalize_whitespace(search_pattern, preserve_structure=True)
    normalized_content = normalize_whitespace(file_content, preserve_structure=True)
    
    # Split both texts into lines for line-by-line comparison
    pattern_lines = normalized_search.splitlines()
    content_lines = normalized_content.splitlines()
    
    # Prepare to capture the best match
    best_start_index = -1
    best_end_index = -1
    best_ratio = 0.0
    
    # Sliding window approach to find best matching block
    pattern_len = len(pattern_lines)
    for i in range(len(content_lines) - pattern_len + 1):
        # Extract a window of lines from content
        window = content_lines[i:i+pattern_len]
        
        # Calculate similarity ratio for this window
        ratio = difflib.SequenceMatcher(None, pattern_lines, window).ratio()
        
        if ratio > best_ratio:
            best_ratio = ratio
            best_start_index = i
            best_end_index = i + pattern_len
    
    # If we found a good match
    if best_ratio > 0.7 and best_start_index >= 0:
        # Get the original text from the file content
        original_content_lines = file_content.splitlines()
        
        # Try to extend the match to include surrounding context
        extended_start = max(0, best_start_index - 2)
        extended_end = min(len(original_content_lines), best_end_index + 2)
        
        matched_text = '\n'.join(original_content_lines[extended_start:extended_end])
        
        return matched_text, best_ratio
    
    # If all else fails, try a direct sequence matcher on the full content
    direct_ratio = difflib.SequenceMatcher(None, search_pattern, file_content).ratio()
    
    if direct_ratio > 0.7:
        # If there's a decent overall match, use a chunking approach
        chunks = []
        chunk_size = 50  # Characters per chunk
        for i in range(0, len(file_content), chunk_size):
            chunk = file_content[i:i+chunk_size*2]  # Overlap chunks
            chunk_ratio = difflib.SequenceMatcher(None, search_pattern, chunk).ratio()
            chunks.append((chunk, chunk_ratio))
        
        best_chunk = max(chunks, key=lambda x: x[1])
        if best_chunk[1] > 0.7:
            return best_chunk[0], best_chunk[1]
    
    # Try line-by-line fuzzy matching as a last resort
    original_lines = file_content.splitlines()
    search_lines = search_pattern.splitlines()
    
    # Find individual line matches
    line_matches = []
    for search_line in search_lines:
        if not search_line.strip():  # Skip empty lines
            continue
        
        best_line_match = None
        best_line_ratio = 0
        
        for orig_line in original_lines:
            if not orig_line.strip():  # Skip empty lines
                continue
                
            line_ratio = difflib.SequenceMatcher(None, search_line, orig_line).ratio()
            if line_ratio > best_line_ratio and line_ratio > 0.8:
                best_line_ratio = line_ratio
                best_line_match = orig_line
        
        if best_line_match:
            line_matches.append((search_line, best_line_match, best_line_ratio))
    
    # If we found good matches for at least 70% of non-empty lines
    if line_matches and len(line_matches) >= 0.7 * len([l for l in search_lines if l.strip()]):
        # Calculate the average match ratio
        avg_ratio = sum(match[2] for match in line_matches) / len(line_matches)
        
        # Extract a segment of the file that contains most of these lines
        matched_lines = [match[1] for match in line_matches]
        matched_indices = [original_lines.index(line) for line in matched_lines if line in original_lines]
        
        if matched_indices:
            start_idx = max(0, min(matched_indices) - 2)
            end_idx = min(len(original_lines), max(matched_indices) + 3)
            
            matched_segment = '\n'.join(original_lines[start_idx:end_idx])
            return matched_segment, avg_ratio
    
    # Return None if no good match found
    return None, 0.0

def perform_contextual_replacement(content: str, matched_text: str, replacement: str, file_path: str) -> bool:
    """Perform a context-aware replacement in a file.
    
    Args:
        content: The full content of the file
        matched_text: The text to replace (approximately matched)
        replacement: The new text to insert
        file_path: The path to the file (for saving)
        
    Returns:
        True if replacement was performed successfully, False otherwise
    """
    try:
        # Split into lines for context analysis
        content_lines = content.splitlines()
        matched_lines = matched_text.splitlines()
        
        # Find all potential matches in the content
        potential_matches = []
        for i in range(len(content_lines) - len(matched_lines) + 1):
            window = content_lines[i:i + len(matched_lines)]
            similarity = difflib.SequenceMatcher(None, window, matched_lines).ratio()
            if similarity > 0.8:
                potential_matches.append((i, similarity))
        
        # Sort by similarity (highest first)
        potential_matches.sort(key=lambda x: x[1], reverse=True)
        
        if not potential_matches:
            logger.debug("No potential matches found for contextual replacement")
            return False
        
        # If there's a clear best match (significantly better than others)
        if len(potential_matches) == 1 or potential_matches[0][1] > potential_matches[1][1] + 0.1:
            best_match_idx = potential_matches[0][0]
            
            # Create new content with replacement
            new_lines = content_lines.copy()
            new_lines[best_match_idx:best_match_idx + len(matched_lines)] = replacement.splitlines()
            
            # Write the file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write('\n'.join(new_lines))
            
            logger.info(f"Applied contextual replacement at line {best_match_idx}")
            return True
            
        # If there are multiple similar matches, need more context to disambiguate
        elif len(potential_matches) > 1:
            logger.debug(f"Multiple potential matches found: {len(potential_matches)}")
            return False
    
    except Exception as e:
        logger.error(f"Error in contextual replacement: {str(e)}")
        return False
    
    return False

def perform_normalized_replacement(content: str, search_pattern: str, replacement: str, file_path: str) -> bool:
    """Perform replacement based on normalized whitespace comparison.
    
    Args:
        content: The full content of the file
        search_pattern: The original search pattern
        replacement: The new text to insert
        file_path: The path to the file (for saving)
        
    Returns:
        True if replacement was performed successfully, False otherwise
    """
    try:
        # Normalize line endings in both search pattern and file content
        search_pattern = normalize_line_endings(search_pattern)
        content = normalize_line_endings(content)
        
        # Try with structure-preserving normalization first
        norm_search = normalize_whitespace(search_pattern, preserve_structure=True)
        norm_content = normalize_whitespace(content, preserve_structure=True)
        
        search_lines = search_pattern.splitlines()
        content_lines = content.splitlines()
        norm_search_lines = norm_search.splitlines()
        norm_content_lines = norm_content.splitlines()
        
        # Try to locate the pattern in normalized content
        for i in range(len(norm_content_lines) - len(norm_search_lines) + 1):
            window = norm_content_lines[i:i + len(norm_search_lines)]
            window_text = '\n'.join(window)
            
            # Compare normalized window to normalized search
            ratio = difflib.SequenceMatcher(None, norm_search, window_text).ratio()
            
            if ratio > 0.9:  # High confidence match
                # Get the original text from this location
                original_match = '\n'.join(content_lines[i:i + len(norm_search_lines)])
                
                # Perform the replacement
                new_content = content.replace(original_match, replacement)
                
                # Write back to the file
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                
                logger.info(f"Applied normalized replacement at line {i}")
                return True
        
        # If structure-preserving normalization fails, try fuzzy line-by-line matching
        # This is more aggressive but can handle larger differences
        
        # First get all non-empty lines from search pattern
        significant_search_lines = [line for line in search_lines if line.strip()]
        
        # Try to find these lines in the content
        matches = []
        for search_line in significant_search_lines:
            norm_search_line = search_line.strip()
            if not norm_search_line:
                continue
                
            for i, content_line in enumerate(content_lines):
                norm_content_line = content_line.strip()
                if not norm_content_line:
                    continue
                    
                # Compare normalized lines
                if norm_search_line == norm_content_line:
                    matches.append((norm_search_line, i))
        
        # If we found matches for most of the significant lines
        if len(matches) >= 0.7 * len(significant_search_lines):
            # Get the block range
            line_indices = [match[1] for match in matches]
            start_idx = max(0, min(line_indices) - 1)
            end_idx = min(len(content_lines), max(line_indices) + 2)
            
            # Replace this section
            original_segment = '\n'.join(content_lines[start_idx:end_idx])
            
            # Only replace if we're reasonably confident
            norm_original = normalize_whitespace(original_segment)
            norm_search_pattern = normalize_whitespace(search_pattern)
            
            similarity = difflib.SequenceMatcher(None, norm_original, norm_search_pattern).ratio()
            if similarity >= 0.7:
                # Create new content with replaced segment
                before = '\n'.join(content_lines[:start_idx])
                after = '\n'.join(content_lines[end_idx:])
                
                # Determine appropriate indentation for replacement
                leading_spaces = []
                for line in content_lines[start_idx:end_idx]:
                    if line.strip():
                        spaces = len(line) - len(line.lstrip())
                        leading_spaces.append(spaces)
                
                if leading_spaces:
                    avg_indent = sum(leading_spaces) // len(leading_spaces)
                    indented_replacement = '\n'.join(f"{' ' * avg_indent}{line}" for line in replacement.splitlines())
                else:
                    indented_replacement = replacement
                
                # Combine the parts
                if before and after:
                    new_content = f"{before}\n{indented_replacement}\n{after}"
                elif before:
                    new_content = f"{before}\n{indented_replacement}"
                elif after:
                    new_content = f"{indented_replacement}\n{after}"
                else:
                    new_content = indented_replacement
                
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                
                logger.info(f"Applied fuzzy replacement between lines {start_idx}-{end_idx}")
                return True
    
    except Exception as e:
        logger.error(f"Error in normalized replacement: {str(e)}")
        return False
    
    return False

def apply_changes(changes: List[FileChange], repo_path: str) -> List[Tuple[FileChange, bool, Optional[str]]]:
    """Apply a list of FileChange objects to a repository.
    
    Args:
        changes: A list of FileChange objects
        repo_path: The absolute path to the repository root
        
    Returns:
        A list of tuples containing (FileChange, success, error_message)
    """
    results = []
    
    for change in changes:
        success = True
        error_message = None
        
        try:
            # Handle both absolute and relative paths
            if os.path.isabs(change.path):
                full_path = change.path
            else:
                full_path = os.path.join(repo_path, change.path)
            
            # Log the operation for debugging
            logger.debug(f"Applying {change.operation} to {full_path}")
            
            if change.operation == "CREATE":
                if change.code is None:
                    error_message = "No file content provided for CREATE operation"
                    success = False
                    continue
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Write the file
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(change.code)
            
            elif change.operation == "UPDATE":
                if change.code is None:
                    error_message = "No file content provided for UPDATE operation"
                    success = False
                    continue
                
                # Ensure directory exists
                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                
                # Write the file
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(change.code)
            
            elif change.operation == "MODIFY":
                if change.code is None:
                    error_message = "No replacement content provided for MODIFY operation"
                    success = False
                    continue
                
                if change.search is None:
                    error_message = "No search pattern provided for MODIFY operation"
                    success = False
                    continue
                
                # Check if file exists
                if not os.path.exists(full_path):
                    error_message = f"File {full_path} does not exist for MODIFY operation"
                    success = False
                    continue
                
                # Read the current file content
                with open(full_path, "r", encoding="utf-8") as f:
                    current_content = f.read()
                
                # Try to find the best match for the search pattern
                matched_text, match_ratio = find_closest_match(change.search, current_content)
                
                if matched_text and match_ratio >= 0.98:
                    # Almost exact match, safe to replace
                    logger.debug(f"Found exact match with ratio {match_ratio:.2f}")
                    new_content = current_content.replace(matched_text, change.code)
                    
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(new_content)
                    
                    logger.info(f"Applied exact replacement for {full_path}")
                
                elif matched_text and match_ratio >= 0.8:
                    # Good match but not exact, check if unique
                    occurrences = current_content.count(matched_text)
                    
                    if occurrences == 1:
                        # Only one occurrence, safe to replace
                        logger.debug(f"Found good unique match with ratio {match_ratio:.2f}")
                        new_content = current_content.replace(matched_text, change.code)
                        
                        with open(full_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        
                        logger.info(f"Applied close match replacement for {full_path}")
                    else:
                        # Multiple occurrences, try more precise matching
                        logger.debug(f"Found multiple occurrences ({occurrences}) of matched text")
                        
                        # Try with context-aware replacement
                        if perform_contextual_replacement(current_content, matched_text, change.code, full_path):
                            success = True
                        else:
                            error_message = f"Multiple matches found ({occurrences}) but couldn't determine which to replace"
                            success = False
                
                elif matched_text and match_ratio >= 0.7:
                    # Moderate match, try string distance and fuzzy replacement
                    logger.debug(f"Found moderate match with ratio {match_ratio:.2f}")
                    
                    # Try line-by-line contextual replacement
                    if perform_contextual_replacement(current_content, matched_text, change.code, full_path):
                        success = True
                    else:
                        error_message = f"Moderate match found (ratio: {match_ratio:.2f}) but replacement is uncertain"
                        success = False
                
                else:
                    # No good match found, try whitespace-normalized comparison
                    normalized_search = normalize_whitespace(change.search)
                    normalized_content = normalize_whitespace(current_content)
                    
                    if normalized_search in normalized_content:
                        # Found match with normalized whitespace, try smart replacement
                        logger.debug("Found match with normalized whitespace")
                        
                        # Try to locate the original segment using normalized search as a guide
                        if perform_normalized_replacement(current_content, change.search, change.code, full_path):
                            success = True
                        else:
                            error_message = "Found match with normalized whitespace but couldn't safely apply replacement"
                            success = False
                    else:
                        # If all attempts fail, report an error
                        error_message = f"Search pattern not found in {full_path}"
                        logger.debug(f"Search pattern: '{change.search}'")
                        logger.debug(f"First 100 chars of file content: '{current_content[:100]}'")
                        success = False
            
            elif change.operation == "DELETE":
                # Check if file exists before deleting
                if os.path.exists(full_path):
                    os.remove(full_path)
                else:
                    logger.warning(f"File {full_path} does not exist, cannot delete")
            
            else:
                error_message = f"Unknown operation: {change.operation}"
                success = False
        
        except Exception as e:
            success = False
            error_message = str(e)
            logger.error(f"Error applying change to {change.path}: {str(e)}")
        
        results.append((change, success, error_message))
    
    return results

def preview_changes(changes: List[FileChange], repo_path: str) -> List[Dict[str, Any]]:
    """Generate a preview of the changes to be applied.
    
    Args:
        changes: A list of FileChange objects
        repo_path: The absolute path to the repository root
        
    Returns:
        A list of dictionaries with preview information
    """
    previews = []
    
    for change in changes:
        preview = {
            "operation": change.operation,
            "path": change.path,
            "exists": False,
            "has_diff": False,
            "diff": None,
            "summary": change.summary
        }
        
        # Handle both absolute and relative paths
        if os.path.isabs(change.path):
            full_path = change.path
        else:
            full_path = os.path.join(repo_path, change.path)
            
        file_exists = os.path.exists(full_path)
        preview["exists"] = file_exists
        
        if change.operation == "CREATE":
            preview["status"] = "Will create new file"
            if file_exists:
                preview["warning"] = "File already exists and will be overwritten"
                preview["has_diff"] = True
                # We could add a diff here between existing and new content
        
        elif change.operation == "UPDATE":
            if file_exists:
                preview["status"] = "Will update existing file"
                # We could add a diff here between existing and new content
                preview["has_diff"] = True
            else:
                preview["status"] = "Will create new file (marked as UPDATE)"
                preview["warning"] = "File doesn't exist but will be created"
        
        elif change.operation == "MODIFY":
            if not file_exists:
                preview["status"] = "Cannot modify (file doesn't exist)"
                preview["warning"] = "File doesn't exist"
                continue
            
            # Check if search pattern exists in the file
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    current_content = f.read()
                
                # Try to find the best match for the search pattern
                matched_text, match_ratio = find_closest_match(change.search, current_content)
                
                if matched_text and match_ratio >= 0.98:
                    # Almost exact match
                    preview["status"] = "Will perform partial modification"
                    preview["has_diff"] = True
                    
                    occurrences = current_content.count(matched_text)
                    if occurrences > 1:
                        preview["warning"] = f"Search pattern found {occurrences} times - all will be replaced"
                
                elif matched_text and match_ratio >= 0.8:
                    # Good match but not exact
                    preview["status"] = "Will perform partial modification (using close match)"
                    preview["has_diff"] = True
                    
                    occurrences = current_content.count(matched_text)
                    if occurrences > 1:
                        preview["warning"] = f"Similar pattern found {occurrences} times - will try contextual replacement"
                    else:
                        preview["warning"] = f"Using close pattern match (similarity: {match_ratio:.2f}) - verify results"
                
                elif matched_text and match_ratio >= 0.7:
                    # Moderate match
                    preview["status"] = "Will attempt partial modification (moderate match)"
                    preview["has_diff"] = True
                    preview["warning"] = f"Using moderate pattern match (similarity: {match_ratio:.2f}) - verify results carefully"
                
                else:
                    # Try with normalized whitespace
                    normalized_search = normalize_whitespace(change.search)
                    normalized_content = normalize_whitespace(current_content)
                    
                    if normalized_search in normalized_content:
                        preview["status"] = "Will attempt modification (whitespace differences)"
                        preview["has_diff"] = True
                        preview["warning"] = "Search pattern found with whitespace differences - will try smart replacement"
                    else:
                        # Structure-preserving normalization
                        normalized_search = normalize_whitespace(change.search, preserve_structure=True)
                        normalized_content = normalize_whitespace(current_content, preserve_structure=True)
                        
                        if normalized_search in normalized_content:
                            preview["status"] = "Will attempt modification (formatting differences)"
                            preview["has_diff"] = True
                            preview["warning"] = "Search pattern found with formatting differences - will try smart replacement"
                        else:
                            preview["status"] = "Cannot modify (search pattern not found)"
                            preview["warning"] = "Search pattern not found in file"
            except Exception as e:
                preview["status"] = f"Error reading file: {str(e)}"
                preview["warning"] = "Cannot preview changes due to error"
        
        elif change.operation == "DELETE":
            if file_exists:
                preview["status"] = "Will delete file"
            else:
                preview["status"] = "Cannot delete (file doesn't exist)"
                preview["warning"] = "File doesn't exist"
        
        previews.append(preview)
    
    return previews