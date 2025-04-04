#!/usr/bin/env python3
"""XML parser module for handling repository changes."""

import os
import re
import logging
from typing import List, Dict, Tuple, Optional, Any, Union
from xml.dom import minidom
import xml.etree.ElementTree as ET
import html
from pathlib import Path
import difflib

# Configure logging
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
        # Ensure operation is a string and convert to uppercase
        if operation is None:
            operation = "UPDATE"  # Default to UPDATE if None
        elif not isinstance(operation, str):
            operation = str(operation)  # Convert non-string types to string
            
        self.operation = operation.upper()
        
        # Ensure path is a string
        if not isinstance(path, str):
            path = str(path)
            
        self.path = path
        
        # Handle code
        if code is not None and not isinstance(code, str):
            code = str(code)
            
        self.code = code
        
        # Handle search
        if search is not None and not isinstance(search, str):
            search = str(search)
            
        self.search = search
        
        # Handle summary
        if summary is not None and not isinstance(summary, str):
            summary = str(summary)
            
        self.summary = summary
    
    def __repr__(self) -> str:
        """Return a string representation of the FileChange object."""
        return f"FileChange({self.operation}, {self.path})"
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FileChange':
        """Create a FileChange object from a dictionary.
        
        Args:
            data: Dictionary containing file change data
            
        Returns:
            A new FileChange object
            
        Raises:
            ValueError: If required fields are missing
        """
        # Extract required fields with fallbacks
        operation = data.get('operation', data.get('action', None))
        path = data.get('path', None)
        
        if not path:
            raise ValueError("Missing required 'path' field")
            
        # Create FileChange from dictionary
        return cls(
            operation=operation,
            path=path,
            code=data.get('code', data.get('content', None)),
            search=data.get('search', None),
            summary=data.get('summary', data.get('description', None))
        )

def extract_xml_from_markdown(text: str) -> str:
    """Extract XML content from markdown code blocks if present.
    
    Args:
        text: The text that may contain markdown-formatted XML
        
    Returns:
        The extracted XML content or the original text if no code blocks found
    """
    # Don't process text that already has XML tags at the beginning
    if text.lstrip().startswith('<'):
        return text
    
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
    """Extract content between various delimiter patterns with improved robustness.
    
    This function handles multiple delimiter formats including:
    - Standard === delimiters
    - Code block ``` delimiters
    - Alternative --- delimiters
    - Comment-style delimiters
    - Custom delimiters with or without whitespace
    
    Args:
        text: The text that may contain content between delimiters
        
    Returns:
        The content between the delimiters or the original text if no delimiters found
    """
    # Handle empty or None input
    if not text:
        return text
        
    # Handle case where text is just delimiters
    if text.strip() in ["===", "```", "---"]:
        return ""
    
    # Try different delimiter patterns
    delimiter_patterns = [
        r"===\s*\n(.*?)\n\s*===",  # Standard format
        r"```\s*\n(.*?)\n\s*```",  # Code block format
        r"---\s*\n(.*?)\n\s*---",  # Alternative delimiter
        r"//\s*===\s*\n(.*?)\n\s*//\s*===",  # Comment-style delimiters
        r"/\*\s*===\s*\n(.*?)\n\s*\*/\s*===",  # C-style comment delimiters
        r"<!--\s*===\s*\n(.*?)\n\s*-->\s*===",  # HTML-style comment delimiters
        r"\*\*\*\s*\n(.*?)\n\s*\*\*\*",  # Alternative asterisk delimiters
        r"<<<\s*\n(.*?)\n\s*>>>",  # Arrow-style delimiters
        r"'''\s*\n(.*?)\n\s*'''",  # Python-style triple quote delimiters
        r'"""\s*\n(.*?)\n\s*"""',  # Python-style triple double-quote delimiters
    ]
    
    for pattern in delimiter_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).rstrip()
    
    # Original implementation as fallback
    lines = text.split('\n')
    
    # Try to find start and end delimiter lines with more flexible matching
    start_idx = -1
    end_idx = -1
    
    # Common delimiter strings to check for
    delimiters = ["===", "```", "---", "***", "<<<", ">>>", "'''", '"""']
    
    for i, line in enumerate(lines):
        stripped_line = line.strip()
        # Check if the line consists mainly of a delimiter pattern (allowing for some extra chars)
        for delimiter in delimiters:
            if delimiter in stripped_line and (
                # Pure delimiter
                stripped_line == delimiter or 
                # Delimiter with comments around it
                re.match(r'^\s*(?://|/\*|\*/|<!--|-->)?\s*' + re.escape(delimiter) + r'\s*(?://|/\*|\*/|<!--|-->)?\s*$', stripped_line)
            ):
                if start_idx == -1:
                    start_idx = i
                    # Remember which delimiter we found
                    found_delimiter = delimiter
                    break
                elif start_idx != -1:
                    # Prefer matching end delimiter to be the same as start delimiter
                    if delimiter == found_delimiter:
                        end_idx = i
                        break
    
    # If we found both delimiters, extract the content between them
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        content = '\n'.join(lines[start_idx + 1:end_idx])
        # Remove any trailing whitespace from the content
        return content.rstrip()
    
    # If we didn't find standard delimiters, try to detect content wrapped in delimiters on same line
    # Example: === content ===
    for delimiter in delimiters:
        pattern = re.escape(delimiter) + r'\s*(.*?)\s*' + re.escape(delimiter)
        match = re.search(pattern, text, re.DOTALL)
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
    
    This function is flexible and can handle various XML formats as long as they contain
    file elements with the required attributes and content. It supports:
    1. Elements with path/action attributes
    2. Elements with nested operation/path/content tags
    3. Various attribute formats (quoted, unquoted, different orders)
    4. XML with or without a root element
    
    Args:
        xml_string: The XML string to parse
        
    Returns:
        A list of FileChange objects representing the changes
        
    Raises:
        XMLParserError: If the XML string is invalid or cannot be parsed
    """
    try:
        # Basic validation before further processing
        if not xml_string or not xml_string.strip():
            raise XMLParserError("Empty XML string provided")
            
        # Special handling for XML content wrapped in formatting instructions
        # First, find any <file ... tags in the content
        file_tag_pattern = r'<file\s+path=["\']'
        file_matches = list(re.finditer(file_tag_pattern, xml_string, re.DOTALL))
        
        # Check if we have <xml_formatting_instructions> and then one or more file tags
        if '<xml_formatting_instructions>' in xml_string:
            if file_matches:
                # Extract from the last file tag (after all the examples in the instructions)
                start_pos = file_matches[-1].start()
                # Verify this is a real file element, not part of examples section
                if '<file path="Models/User.swift" action="modify">' in xml_string[start_pos:start_pos+100]:
                    xml_string = xml_string[start_pos:]
                    logger.debug("Extracted actual XML file changes from formatting instructions")
                else:
                    # Try the second-to-last match or continue through file matches until we find a real one
                    for i in range(len(file_matches)-1, -1, -1):
                        pos = file_matches[i].start()
                        if '<file path="Models/User.swift" action="modify">' in xml_string[pos:pos+100]:
                            xml_string = xml_string[pos:]
                            logger.debug("Found actual file changes after examples in instructions")
                            break
            else:
                # No file tags found, this is just instructions
                raise XMLParserError("Found formatting instructions but no file changes")
        
        # If we still have text before the first file tag (like Plan blocks or other text)
        # and there are file tags present, extract from the first file tag
        elif not xml_string.lstrip().startswith('<file') and file_matches:
            xml_string = xml_string[file_matches[0].start():]
            logger.debug("Extracted content starting from first file tag")
        
        # Try to extract XML content from code blocks if necessary, but only
        # if the string doesn't already start with an XML tag
        if not xml_string.lstrip().startswith('<'):
            extracted = extract_xml_from_markdown(xml_string)
            if extracted != xml_string:
                xml_string = extracted
                logger.debug("Extracted XML content from markdown")
        
        # Check for obvious XML-like content - must contain at least one angle bracket
        if '<' not in xml_string:
            raise XMLParserError("Invalid XML format: missing angle brackets")
        
        # Clean up the XML string - trim whitespace
        xml_string = xml_string.strip()
        
        # Remove Plan tags which are for documentation only and not part of changes
        xml_string = re.sub(r'<Plan>.*?</Plan>', '', xml_string, flags=re.DOTALL)
        
        # Also remove any HTML comment blocks
        xml_string = re.sub(r'<!--.*?-->', '', xml_string, flags=re.DOTALL)
        
        # Validate XML structure before attempting to parse
        is_valid, error_message = validate_xml_structure(xml_string)
        if not is_valid:
            logger.warning(f"XML structure validation failed: {error_message}")
            logger.debug("Will attempt to recover and parse anyway")
            # Don't raise an exception here, try to parse anyway
        
        # Check if the XML has a root element - checking just startswith/endswith is not reliable
        # due to potential whitespace, so use a more flexible approach
        xml_string = xml_string.strip()
        
        # Simple check for angle brackets
        if not (xml_string.startswith('<') and '>' in xml_string):
            raise XMLParserError("Invalid XML format: missing angle brackets")
            
        # Check for proper root element with regex that allows for whitespace
        root_pattern = r'^\s*<[^>]+>.*</[^>]+>\s*$'
        has_root = re.match(root_pattern, xml_string, re.DOTALL)
        
        if not has_root:
            # Try to detect if we have just orphaned file elements 
            if re.search(r'^\s*<file', xml_string, re.DOTALL) and re.search(r'</file>\s*$', xml_string, re.DOTALL):
                xml_string = f"<root>{xml_string}</root>"
                logger.debug("Wrapped orphaned file elements in root tag")
            else:
                # Try harder to detect valid but unrooted XML
                open_tags = re.findall(r'<([a-zA-Z][a-zA-Z0-9_:-]*)[^>]*>', xml_string)
                close_tags = re.findall(r'</([a-zA-Z][a-zA-Z0-9_:-]*)>', xml_string)
                
                if open_tags and close_tags and open_tags[0] == close_tags[-1]:
                    # First open tag matches last closing tag, might be valid XML
                    logger.debug(f"XML appears to have a root element: {open_tags[0]}")
                else:
                    logger.debug("XML doesn't have a proper root element, wrapping in root tag")
                    xml_string = f"<root>{xml_string}</root>"
        
        # Normalize XML by handling common issues
        # - Replace non-breaking spaces with regular spaces
        xml_string = xml_string.replace('\xa0', ' ')
        
        # Track parsing attempts for better error reporting
        parsing_attempts = []
        all_changes = []
        
        # First try to parse using the code_changes format (more flexible)
        try:
            changes = parse_code_changes_format(xml_string)
            if changes:
                # Filter to ensure we only have valid FileChange objects
                valid_changes = ensure_valid_file_changes(changes)
                parsing_attempts.append(("code_changes_format", len(valid_changes), None))
                all_changes.extend(valid_changes)
                logger.debug(f"Successfully parsed {len(valid_changes)} changes using code_changes_format")
        except Exception as e:
            logger.debug(f"Failed to parse as code_changes format: {str(e)}")
            parsing_attempts.append(("code_changes_format", 0, str(e)))
        
        # If that fails or finds no changes, try the changed_files format
        if not all_changes:
            try:
                changes = parse_changed_files_format(xml_string)
                if changes:
                    # Filter to ensure we only have valid FileChange objects
                    valid_changes = ensure_valid_file_changes(changes)
                    parsing_attempts.append(("changed_files_format", len(valid_changes), None))
                    all_changes.extend(valid_changes)
                    logger.debug(f"Successfully parsed {len(valid_changes)} changes using changed_files_format")
            except Exception as e:
                logger.debug(f"Failed to parse as changed_files format: {str(e)}")
                parsing_attempts.append(("changed_files_format", 0, str(e)))
        
        # If both specific formats fail or find no changes, try a more generic approach
        if not all_changes:
            try:
                # Use minidom for parsing
                try:
                    dom = minidom.parseString(xml_string)
                except Exception as dom_error:
                    # If pure XML parsing fails, try to clean up the XML first
                    logger.debug(f"Minidom parsing failed: {str(dom_error)}")
                    
                    # Try to fix common XML issues
                    cleaned_xml = sanitize_xml(xml_string)
                    dom = minidom.parseString(cleaned_xml)
                
                # Find all file elements, regardless of where they are in the tree
                file_nodes = dom.getElementsByTagName("file")
                if not file_nodes:
                    parsing_attempts.append(("generic_minidom", 0, "No 'file' elements found"))
                    logger.debug("No 'file' elements found in XML with generic approach")
                else:
                    changes = []
                    for file_node in file_nodes:
                        try:
                            # Parse each file node with flexible attribute/element handling
                            change = parse_file_node(file_node)
                            if change:
                                changes.append(change)
                        except Exception as node_error:
                            logger.error(f"Error processing file element: {str(node_error)}")
                            continue
                    
                    if changes:
                        valid_changes = ensure_valid_file_changes(changes)
                        parsing_attempts.append(("generic_minidom", len(valid_changes), None))
                        all_changes.extend(valid_changes)
                        logger.debug(f"Successfully parsed {len(valid_changes)} changes using generic minidom approach")
            except Exception as e:
                logger.debug(f"Failed to parse using generic approach: {str(e)}")
                parsing_attempts.append(("generic_minidom", 0, str(e)))
        
        # If all structured parsing approaches fail, try regex-based parsing as a last resort
        if not all_changes:
            try:
                changes = parse_with_regex(xml_string)
                if changes:
                    valid_changes = ensure_valid_file_changes(changes)
                    parsing_attempts.append(("regex_parser", len(valid_changes), None))
                    all_changes.extend(valid_changes)
                    logger.debug(f"Successfully parsed {len(valid_changes)} changes using regex fallback")
            except Exception as e:
                logger.debug(f"Failed to parse using regex approach: {str(e)}")
                parsing_attempts.append(("regex_parser", 0, str(e)))
        
        # If we found any valid changes from any method, return them
        if all_changes:
            # Log the path and operation for each change found
            for change in all_changes:
                logger.debug(f"Found valid change: {change.operation} for {change.path}")
                
            return all_changes
            
        # If we get here, no parsing method succeeded
        error_details = '\n'.join([f"- {method}: {count} changes found{f' ({error})' if error else ''}" 
                                   for method, count, error in parsing_attempts])
        raise XMLParserError(f"Could not parse XML in any supported format. Attempts:\n{error_details}")
            
    except XMLParserError:
        # Re-raise specific XML parser errors
        raise
    except Exception as e:
        logger.error(f"Error in parse_xml_string: {str(e)}")
        raise XMLParserError(f"Failed to parse XML: {str(e)}")

def ensure_valid_file_changes(changes: List[Any]) -> List[FileChange]:
    """Ensure all items in the changes list are valid FileChange objects.
    
    This function filters and converts items to ensure they're all valid FileChange objects.
    
    Args:
        changes: List of objects that should be FileChange instances
        
    Returns:
        List containing only valid FileChange objects
    """
    valid_changes = []
    
    for change in changes:
        if isinstance(change, FileChange):
            # Already a valid FileChange object
            valid_changes.append(change)
        elif isinstance(change, dict):
            # Try to convert dict to FileChange
            try:
                # Get required fields with fallbacks
                operation = change.get('operation', change.get('action', None))
                path = change.get('path', None)
                
                if operation and path:
                    # Create FileChange from dict
                    file_change = FileChange(
                        operation=operation,
                        path=path,
                        code=change.get('code', change.get('content', None)),
                        search=change.get('search', None),
                        summary=change.get('summary', change.get('description', None))
                    )
                    valid_changes.append(file_change)
                else:
                    logger.warning(f"Skipping invalid dict, missing required fields: {change}")
            except Exception as e:
                logger.warning(f"Failed to convert dict to FileChange: {str(e)}")
        elif isinstance(change, str):
            # Skip strings entirely, they can't be converted to FileChange
            logger.warning(f"Skipping string value, not a valid FileChange: {repr(change[:50])}...")
        else:
            logger.warning(f"Skipping invalid object of type {type(change)}")
    
    return valid_changes

def parse_file_node(file_node) -> Optional[FileChange]:
    """Parse a file node from a minidom document.
    
    This is a flexible parsing function that tries multiple approaches
    to extract information from file nodes.
    
    Args:
        file_node: A minidom Element representing a file node
        
    Returns:
        FileChange object or None if parsing fails
    """
    # Try to get operation and path from attributes first
    operation = None
    path = None
    
    # Check for various attribute names for operation
    for attr_name in ['action', 'operation', 'type']:
        if file_node.hasAttribute(attr_name):
            operation = file_node.getAttribute(attr_name).strip().upper()
            break
    
    # Check path attribute
    if file_node.hasAttribute("path"):
        path = file_node.getAttribute("path").strip()
    
    # If attributes not found, try child elements
    if not operation:
        for element_name in ['operation', 'action', 'type']:
            operation_nodes = file_node.getElementsByTagName(element_name)
            if operation_nodes and operation_nodes[0].firstChild:
                operation = operation_nodes[0].firstChild.nodeValue.strip().upper()
                break
    
    if not path:
        for element_name in ['path', 'filepath', 'file_path']:
            path_nodes = file_node.getElementsByTagName(element_name)
            if path_nodes and path_nodes[0].firstChild:
                path = path_nodes[0].firstChild.nodeValue.strip()
                break
    
    # Validate required fields
    if not path:
        logger.warning("No path found for file element, skipping")
        return None
    
    if not operation:
        # Try to infer operation from node structure
        if file_node.getElementsByTagName("search") and file_node.getElementsByTagName("content"):
            operation = "MODIFY"
            logger.debug(f"Inferred MODIFY operation for {path}")
        else:
            # Default to UPDATE if we can't determine the operation
            operation = "UPDATE"
            logger.debug(f"Defaulted to UPDATE operation for {path}")
    
    # Normalize operation names
    if operation in ["REWRITE", "REPLACE"]:
        operation = "UPDATE"
    
    # Get content if available
    code = None
    # Check various element names for content
    for content_name in ['content', 'code', 'file_code']:
        content_nodes = file_node.getElementsByTagName(content_name)
        if content_nodes and content_nodes[0].firstChild:
            code = content_nodes[0].firstChild.nodeValue
            # Try to extract content between delimiters if present
            code = extract_content_between_delimiters(code)
            break
    
    # Get search pattern if available
    search = None
    # Check various element names for search
    for search_name in ['search', 'file_search']:
        search_nodes = file_node.getElementsByTagName(search_name)
        if search_nodes and search_nodes[0].firstChild:
            search = search_nodes[0].firstChild.nodeValue
            # Try to extract content between delimiters if present
            search = extract_content_between_delimiters(search)
            break
    
    # Get summary if available
    summary = None
    # Check various element names for summary/description
    for desc_name in ['summary', 'description', 'file_summary', 'desc']:
        summary_nodes = file_node.getElementsByTagName(desc_name)
        if summary_nodes and summary_nodes[0].firstChild:
            summary = summary_nodes[0].firstChild.nodeValue.strip()
            break
    
    # Look for change blocks if they exist
    change_nodes = file_node.getElementsByTagName("change")
    if change_nodes:
        # Process the first change node (for simplicity)
        change_node = change_nodes[0]
        
        # Try to extract description, search, and content from change node
        if not summary:
            desc_nodes = change_node.getElementsByTagName("description")
            if desc_nodes and desc_nodes[0].firstChild:
                summary = desc_nodes[0].firstChild.nodeValue.strip()
        
        if not search:
            search_nodes = change_node.getElementsByTagName("search")
            if search_nodes and search_nodes[0].firstChild:
                search_text = search_nodes[0].firstChild.nodeValue
                search = extract_content_between_delimiters(search_text)
        
        if not code:
            content_nodes = change_node.getElementsByTagName("content")
            if content_nodes and content_nodes[0].firstChild:
                content_text = content_nodes[0].firstChild.nodeValue
                code = extract_content_between_delimiters(content_text)
    
    # Additional validation and cleanup
    if operation == "MODIFY" and not search:
        logger.warning(f"MODIFY operation requested but no search pattern provided for {path}")
        # Don't fail outright - this will be caught by the apply function
    
    if operation == "DELETE":
        # No content needed for DELETE
        code = ""
    elif not code and operation != "DELETE":
        # If no content found for operations that need it
        logger.warning(f"No content found for {operation} operation on {path}")
        # Allow it to proceed - this will be caught by the apply function
    
    # Create FileChange object
    return FileChange(operation, path, code, search, summary)

def sanitize_xml(xml_string: str) -> str:
    """Clean up XML string to handle common issues.
    
    Args:
        xml_string: The original XML string
        
    Returns:
        The cleaned XML string
    """
    # Replace XML entities with their actual characters
    entity_replacements = {
        '&lt;': '<',
        '&gt;': '>',
        '&amp;': '&',
        '&quot;': '"',
        '&apos;': "'"
    }
    
    for entity, replacement in entity_replacements.items():
        xml_string = xml_string.replace(entity, replacement)
    
    # Fix unclosed tags by detection
    tag_pattern = r'<([a-zA-Z][a-zA-Z0-9_:-]*)[^/>]*?>'
    close_pattern = r'</([a-zA-Z][a-zA-Z0-9_:-]*)>'
    
    open_tags = re.findall(tag_pattern, xml_string)
    close_tags = re.findall(close_pattern, xml_string)
    
    # Detect tags that were opened but not closed
    unclosed = []
    for tag in open_tags:
        if tag not in close_tags and tag not in ['br', 'hr', 'img', 'input', 'meta', 'link']:
            unclosed.append(tag)
    
    # Add missing closing tags at the end
    for tag in reversed(unclosed):
        if xml_string.strip().endswith('>'):
            xml_string += f'</{tag}>'
    
    # Try to fix broken attribute syntax
    # Find attributes missing quotes
    attr_pattern = r'(\w+)=([^"\'\s>][^\s>]*)'
    xml_string = re.sub(attr_pattern, r'\1="\2"', xml_string)
    
    return xml_string

def parse_with_regex(xml_string: str) -> List[FileChange]:
    """Parse XML using regex as a last resort for malformed XML.
    
    Args:
        xml_string: The XML string to parse
        
    Returns:
        List of FileChange objects
    """
    changes = []
    
    # Try different regex patterns to find file blocks
    # Pattern 1: Look for file tags with attributes
    file_patterns = [
        # file tag with path and action attributes in either order
        r'<file\s+(?:path\s*=\s*["\']?(.*?)["\']?\s+action\s*=\s*["\']?(.*?)["\']?|action\s*=\s*["\']?(.*?)["\']?\s+path\s*=\s*["\']?(.*?)["\']?)>(.*?)</file>',
        # Very lenient pattern for badly formed XML
        r'<file[^>]*?(?:path|filepath)\s*=\s*["\']?(.*?)["\']?[^>]*?(?:action|operation|type)\s*=\s*["\']?(.*?)["\']?[^>]*?>(.*?)</file>'
    ]
    
    for pattern in file_patterns:
        matches = re.findall(pattern, xml_string, re.DOTALL | re.IGNORECASE)
        if matches:
            for match in matches:
                try:
                    # Handle different match group structures
                    if len(match) == 5:  # First pattern with path-action or action-path order
                        if match[0] and match[1]:  # path-action order
                            path, action = match[0].strip(), match[1].strip()
                            content = match[4]
                        else:  # action-path order
                            action, path = match[2].strip(), match[3].strip()
                            content = match[4]
                    elif len(match) == 3:  # Simple pattern
                        path, action, content = match
                    
                    path = path.strip()
                    action = action.strip().upper()
                    
                    # Extract search and content from the file content if it has change blocks
                    search = None
                    code = None
                    
                    # Look for change blocks
                    change_match = re.search(r'<change>(.*?)</change>', content, re.DOTALL)
                    if change_match:
                        change_content = change_match.group(1)
                        
                        # Extract description if present
                        desc_match = re.search(r'<description>(.*?)</description>', change_content, re.DOTALL)
                        summary = desc_match.group(1).strip() if desc_match else None
                        
                        # Extract search pattern if present
                        search_match = re.search(r'<search>(.*?)</search>', change_content, re.DOTALL)
                        if search_match:
                            search = extract_content_between_delimiters(search_match.group(1))
                        
                        # Extract content if present
                        content_match = re.search(r'<content>(.*?)</content>', change_content, re.DOTALL)
                        if content_match:
                            code = extract_content_between_delimiters(content_match.group(1))
                    else:
                        # No change blocks, look for direct content
                        content_match = re.search(r'<content>(.*?)</content>', content, re.DOTALL)
                        if content_match:
                            code = extract_content_between_delimiters(content_match.group(1))
                        else:
                            # No structured content, just use the entire file content
                            code = content.strip()
                            
                        # Look for direct search pattern
                        search_match = re.search(r'<search>(.*?)</search>', content, re.DOTALL)
                        if search_match:
                            search = extract_content_between_delimiters(search_match.group(1))
                            
                        # Look for direct description
                        desc_match = re.search(r'<description>(.*?)</description>', content, re.DOTALL)
                        summary = desc_match.group(1).strip() if desc_match else None
                    
                    # Normalize operation name
                    if action in ["REWRITE", "REPLACE"]:
                        action = "UPDATE"
                    
                    # Create FileChange object
                    change = FileChange(action, path, code, search, summary)
                    changes.append(change)
                except Exception as e:
                    logger.warning(f"Error parsing regex match: {str(e)}")
                    continue
            
            if changes:
                break  # If we found changes with this pattern, stop trying others
    
    return changes

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
    """Parse the new <code_changes> format with search/content delimiters.
    
    This function can handle a variety of XML formats with file elements
    and supports multiple attribute styles, nested change blocks, and
    more flexible content formats.
    
    Args:
        xml_string: The XML string to parse
        
    Returns:
        A list of FileChange objects
    """
    changes = []
    
    try:
        # First try to parse using minidom to handle well-formed XML properly
        try:
            dom = minidom.parseString(xml_string)
            file_elements = dom.getElementsByTagName('file')
            
            if file_elements:
                logger.debug(f"Found {len(file_elements)} file elements using minidom")
                
                for file_elem in file_elements:
                    try:
                        # Extract path and action attributes with fallbacks
                        path = None
                        action = None
                        
                        if file_elem.hasAttribute('path'):
                            path = file_elem.getAttribute('path').strip()
                        
                        if file_elem.hasAttribute('action'):
                            action = file_elem.getAttribute('action').strip().upper()
                        elif file_elem.hasAttribute('operation'):
                            action = file_elem.getAttribute('operation').strip().upper()
                        
                        # Validate required attributes
                        if not path:
                            logger.warning("Missing path attribute in file element")
                            continue
                            
                        if not action:
                            logger.warning(f"Missing action attribute in file element for {path}")
                            # Default to UPDATE if no action specified
                            action = "UPDATE"
                        
                        # Normalize operation names
                        if action in ["REWRITE", "REPLACE"]:
                            action = "UPDATE"
                            
                        # Look for change blocks within the file element
                        change_elements = file_elem.getElementsByTagName('change')
                        
                        if change_elements:
                            # Process each change element
                            for change_elem in change_elements:
                                try:
                                    # Extract description if present
                                    summary = None
                                    desc_elems = change_elem.getElementsByTagName('description')
                                    if desc_elems and desc_elems[0].firstChild:
                                        summary = desc_elems[0].firstChild.nodeValue.strip()
                                    
                                    # Extract search pattern if present
                                    search = None
                                    search_elems = change_elem.getElementsByTagName('search')
                                    if search_elems and search_elems[0].firstChild:
                                        search_text = search_elems[0].firstChild.nodeValue
                                        search = extract_content_between_delimiters(search_text)
                                    
                                    # Extract content if present
                                    code = None
                                    content_elems = change_elem.getElementsByTagName('content')
                                    if content_elems and content_elems[0].firstChild:
                                        content_text = content_elems[0].firstChild.nodeValue
                                        code = extract_content_between_delimiters(content_text)
                                    
                                    # Create FileChange object
                                    change = FileChange(action, path, code, search, summary)
                                    changes.append(change)
                                except Exception as change_error:
                                    logger.warning(f"Error processing change element: {str(change_error)}")
                                    continue
                        else:
                            # No change elements, look for direct content
                            code = None
                            search = None
                            
                            # Try to extract direct content
                            content_elems = file_elem.getElementsByTagName('content')
                            if content_elems and content_elems[0].firstChild:
                                content_text = content_elems[0].firstChild.nodeValue
                                code = extract_content_between_delimiters(content_text)
                            else:
                                # If no content element, use text content of the file element
                                code = ''.join([node.nodeValue for node in file_elem.childNodes if node.nodeType == node.TEXT_NODE]).strip()
                                # Check if the code is not empty
                                if not code:
                                    logger.warning(f"No content found for {path}")
                            
                            # Try to extract direct search pattern
                            search_elems = file_elem.getElementsByTagName('search')
                            if search_elems and search_elems[0].firstChild:
                                search_text = search_elems[0].firstChild.nodeValue
                                search = extract_content_between_delimiters(search_text)
                            
                            # Create FileChange object
                            change = FileChange(action, path, code, search, None)
                            changes.append(change)
                    
                    except Exception as file_error:
                        logger.warning(f"Error processing file element: {str(file_error)}")
                        continue
                
                if changes:
                    return changes
                
        except Exception as dom_error:
            logger.debug(f"Minidom parsing failed: {str(dom_error)}")
            # Fall back to regex parsing if minidom fails
        
        # Extract all file elements with various attribute formats using regex
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
        
        # Try one more pattern with very loose attribute matching
        if not file_matches:
            file_pattern = r"<file[^>]*?(?:path|filepath)=[\"\']?([^\"\'>\s]+)[\"\']?[^>]*?(?:action|operation)=[\"\']?([^\"\'>\s]+)[\"\']?[^>]*?>(.*?)</file>"
            file_matches = re.findall(file_pattern, xml_string, re.DOTALL | re.IGNORECASE)
        
        if not file_matches:
            raise XMLParserError("No valid file elements found using regex patterns")
        
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
                    logger.warning(f"Invalid action '{action}' found, defaulting to UPDATE")
                    action = "UPDATE"
                
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
                        logger.warning(f"Error processing change element: {str(e)}")
                        continue
                    
                # If no change blocks were found, treat the entire file content as a single change
                if not change_matches:
                    try:
                        # Skip processing if this looks like a Plan block or other non-change element
                        if re.search(r'<\s*Plan\s*>|<\s*/\s*Plan\s*>', file_content, re.IGNORECASE):
                            logger.debug("Skipping what appears to be a Plan block")
                            continue
                            
                        operation = action
                        if operation == "REWRITE":
                            operation = "UPDATE"
                        
                        # Extra validation to ensure we have required fields
                        if not path or not operation:
                            logger.warning("Missing path or operation, cannot create valid FileChange")
                            continue
                            
                        # Extract content more carefully, handling potential nested tags
                        code_content = file_content.strip()
                        
                        # Try to extract content from <content> tags if present
                        content_match = re.search(r'<content>(.*?)</content>', code_content, re.DOTALL)
                        if content_match:
                            code_content = extract_content_between_delimiters(content_match.group(1))
                            
                        # Try to extract search from <search> tags if present
                        search = None
                        search_match = re.search(r'<search>(.*?)</search>', file_content, re.DOTALL)
                        if search_match:
                            search = extract_content_between_delimiters(search_match.group(1))
                            
                        # Try to extract description if present
                        description = None
                        desc_match = re.search(r'<description>(.*?)</description>', file_content, re.DOTALL)
                        if desc_match:
                            description = desc_match.group(1).strip()
                            
                        # Create properly validated FileChange object
                        change = FileChange(operation, path, code_content, search, description)
                        changes.append(change)
                    except Exception as e:
                        logger.warning(f"Error processing file content: {str(e)}")
                        continue
                    
            except Exception as e:
                logger.warning(f"Error processing file element: {str(e)}")
                continue
        
        # Ensure we have at least one valid change
        if not changes:
            raise XMLParserError("No valid changes found in XML after attempting all patterns")
        
        # Check for and filter any invalid changes
        valid_changes = []
        for i, change in enumerate(changes):
            if not isinstance(change, FileChange):
                logger.warning(f"Skipping invalid object at index {i} of type {type(change)}")
                continue
            valid_changes.append(change)
        
        if not valid_changes:
            raise XMLParserError("No valid FileChange objects found after filtering")
        
        # Log the detected changes for debugging
        for change in valid_changes:
            logger.debug(f"Detected change: {change.operation} for {change.path}")
            if change.search:
                logger.debug(f"Search pattern length: {len(change.search)} characters")
            if change.code:
                logger.debug(f"Content length: {len(change.code)} characters")
        
        return valid_changes
        
    except XMLParserError:
        # Re-raise specific XMLParserErrors with their original message
        raise
    except Exception as e:
        # Wrap generic exceptions with more specific error
        logger.error(f"Error parsing code_changes format XML: {str(e)}")
        raise XMLParserError(f"Failed to parse code_changes format: {str(e)}")

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

def apply_changes(changes_or_xml: Union[List[FileChange], str], repo_path: str, lenient_search: bool = False) -> List[Tuple[FileChange, bool, Optional[str]]]:
    """Apply a list of file changes to a repository.
    
    This function is a compatibility wrapper that supports both:
    1. A list of FileChange objects 
    2. An XML string (for backward compatibility)
    
    Args:
        changes_or_xml: List of FileChange objects or XML string
        repo_path: Path to the repository
        lenient_search: If True, missing search patterns in MODIFY operations
                       are treated as warnings rather than failures
        
    Returns:
        List of tuples containing (FileChange, success, error_message)
    """
    # Check if we're dealing with a string (XML) or list of FileChange objects
    if isinstance(changes_or_xml, str):
        # Parse the XML string to get changes
        try:
            changes = parse_xml_string(changes_or_xml)
        except XMLParserError as e:
            logger.error(f"Error parsing XML: {str(e)}")
            return []
    else:
        changes = changes_or_xml
        
    # Process each change and track results
    results = []
    
    for change in changes:
        try:
            # Skip invalid objects
            if not isinstance(change, FileChange):
                logger.warning(f"Skipping invalid object, not a FileChange: {type(change)}")
                continue
                
            # Apply the change based on operation type
            success = False
            error_message = None
            
            try:
                if change.operation == "CREATE":
                    success = create_file(repo_path, change.path, change.code)
                elif change.operation == "UPDATE":
                    success = update_file(repo_path, change.path, change.code)
                elif change.operation == "DELETE":
                    success = delete_file(repo_path, change.path)
                elif change.operation == "MODIFY":
                    success = modify_file(repo_path, change.path, change.search, change.code, lenient_search)
                else:
                    error_message = f"Unknown operation: {change.operation}"
                    success = False
            except Exception as e:
                error_message = str(e)
                success = False
                
            results.append((change, success, error_message))
                
        except Exception as e:
            # Handle any unexpected errors
            logger.error(f"Error applying change: {str(e)}")
            results.append((change, False, str(e)))
            
    return results

def preview_changes(changes_or_xml: Union[List[FileChange], str], repo_path: str) -> List[Dict[str, Any]]:
    """Generate previews of file changes before applying them.
    
    This function is a compatibility wrapper that supports both:
    1. A list of FileChange objects 
    2. An XML string (for backward compatibility)
    
    Args:
        changes_or_xml: List of FileChange objects or XML string
        repo_path: Path to the repository
        
    Returns:
        List of dictionaries with preview information for each change
    """
    # Check if we're dealing with a string (XML) or list of FileChange objects
    if isinstance(changes_or_xml, str):
        # If it's an XML string, use parse_xml_preview for better handling
        return parse_xml_preview(changes_or_xml, repo_path)
    
    # Process changes and generate previews
    previews = []
    
    for change in changes_or_xml:  # Fixed: was 'changes', now 'changes_or_xml'
        try:
            # Skip invalid objects
            if not isinstance(change, FileChange):
                logger.warning(f"Skipping invalid object, not a FileChange: {type(change)}")
                continue
                
            # Create basic preview info
            preview = {
                "path": change.path,
                "operation": change.operation,
                "operation_desc": f"{change.operation.capitalize()} operation"
            }
            
            # Get absolute path
            file_path = os.path.join(repo_path, change.path)
            file_exists = os.path.exists(file_path)
            preview["file_exists"] = file_exists
            
            # Add operation-specific preview info
            if change.operation == "CREATE":
                preview["operation_desc"] = "Creating new file"
                if change.code:
                    preview["content_preview"] = change.code[:500] + "..." if len(change.code) > 500 else change.code
                if file_exists:
                    preview["warning"] = "File already exists"
                    
            elif change.operation == "UPDATE":
                preview["operation_desc"] = "Updating existing file"
                if change.code:
                    preview["content_preview"] = change.code[:500] + "..." if len(change.code) > 500 else change.code
                if not file_exists:
                    preview["warning"] = "File doesn't exist"
                    
            elif change.operation == "DELETE":
                preview["operation_desc"] = "Deleting file"
                if not file_exists:
                    preview["warning"] = "File doesn't exist"
                    
            elif change.operation == "MODIFY":
                preview["operation_desc"] = "Modifying file content"
                if not file_exists:
                    preview["warning"] = "File doesn't exist"
                elif not change.search:
                    preview["warning"] = "No search pattern provided"
                else:
                    # Check if search pattern exists in file
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            
                        if change.search in content:
                            preview["match_found"] = True
                            preview["search_preview"] = change.search[:200] + "..." if len(change.search) > 200 else change.search
                            preview["replacement_preview"] = change.code[:200] + "..." if change.code and len(change.code) > 200 else change.code
                        else:
                            preview["match_found"] = False
                            preview["warning"] = "Search pattern not found in file"
                    except Exception as e:
                        preview["error"] = f"Error reading file: {str(e)}"
            
            # Add to previews list
            previews.append(preview)
                
        except Exception as e:
            # Handle any unexpected errors
            logger.error(f"Error generating preview: {str(e)}")
            previews.append({
                "path": getattr(change, 'path', 'unknown'),
                "operation": getattr(change, 'operation', 'unknown'),
                "error": f"Error generating preview: {str(e)}"
            })
            
    return previews

def validate_xml_structure(xml_string: str) -> Tuple[bool, Optional[str]]:
    """Basic validation of XML structure before detailed parsing.
    
    This function performs fundamental XML structure validation:
    - Checks for balanced tags
    - Validates that tags are correctly nested
    - Looks for malformed tags or attributes
    - Detects XML syntax errors
    
    Args:
        xml_string: The XML string to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not xml_string or not xml_string.strip():
        return False, "Empty XML string"
    
    try:
        # First try using minidom for a quick validity check
        try:
            minidom.parseString(xml_string)
            # If we get here, the XML is well-formed according to minidom
            return True, None
        except Exception as dom_error:
            # If minidom fails, try our custom validation for more specific error messages
            logger.debug(f"minidom validation failed: {str(dom_error)}")
        
        # Manual tag balancing check to provide better error messages
        tag_stack = []
        i = 0
        line_num = 1
        col_num = 1
        
        # Map to track line and column numbers for better error reporting
        positions = {}
        
        while i < len(xml_string):
            # Track line and column numbers
            if xml_string[i] == '\n':
                line_num += 1
                col_num = 1
            else:
                col_num += 1
                
            if xml_string[i:i+4] == '<!--':
                # Skip comments
                end_comment = xml_string.find('-->', i)
                if end_comment == -1:
                    return False, f"Unterminated comment at line {line_num}, column {col_num}"
                
                # Update line and column for the end of the comment
                comment_text = xml_string[i:end_comment+3]
                lines = comment_text.split('\n')
                if len(lines) > 1:
                    line_num += len(lines) - 1
                    col_num = len(lines[-1])
                else:
                    col_num += len(comment_text)
                
                i = end_comment + 3
            elif xml_string[i] == '<':
                # Record position for this tag
                positions[len(tag_stack)] = (line_num, col_num)
                
                if i+1 < len(xml_string) and xml_string[i+1] == '/':
                    # Closing tag
                    end_tag = xml_string.find('>', i)
                    if end_tag == -1:
                        return False, f"Unterminated closing tag at line {line_num}, column {col_num}"
                    
                    tag_name = xml_string[i+2:end_tag].strip()
                    
                    # Update position info
                    tag_text = xml_string[i:end_tag+1]
                    lines = tag_text.split('\n')
                    if len(lines) > 1:
                        line_num += len(lines) - 1
                        col_num = len(lines[-1])
                    else:
                        col_num += len(tag_text)
                    
                    if not tag_stack:
                        return False, f"Unexpected closing tag </{tag_name}> at line {line_num}, column {col_num}"
                    
                    if tag_stack[-1] != tag_name:
                        open_line, open_col = positions.get(len(tag_stack)-1, (0, 0))
                        return False, f"Mismatched tags: <{tag_stack[-1]}> at line {open_line}, column {open_col} and </{tag_name}> at line {line_num}, column {col_num}"
                    
                    tag_stack.pop()
                    i = end_tag + 1
                else:
                    # Opening tag
                    end_tag = xml_string.find('>', i)
                    if end_tag == -1:
                        return False, f"Unterminated opening tag at line {line_num}, column {col_num}"
                    
                    tag_content = xml_string[i+1:end_tag].strip()
                    
                    # Handle self-closing tags
                    if tag_content.endswith('/'):
                        # Self-closing tag, doesn't need to be pushed to stack
                        tag_content = tag_content[:-1].strip()
                    else:
                        # Normal opening tag, extract tag name
                        if ' ' in tag_content:
                            tag_name = tag_content.split()[0]
                        else:
                            tag_name = tag_content
                            
                        # Don't push special tags to stack
                        if not (tag_name.startswith('!') or tag_name.startswith('?')):
                            tag_stack.append(tag_name)
                    
                    # Check for attribute syntax errors
                    if ' ' in tag_content:
                        attrs_part = tag_content[tag_content.index(' '):]
                        # Look for attribute syntax errors
                        try:
                            validate_attributes(attrs_part)
                        except Exception as attr_error:
                            return False, f"Attribute error in tag at line {line_num}, column {col_num}: {str(attr_error)}"
                    
                    # Update position info
                    tag_text = xml_string[i:end_tag+1]
                    lines = tag_text.split('\n')
                    if len(lines) > 1:
                        line_num += len(lines) - 1
                        col_num = len(lines[-1])
                    else:
                        col_num += len(tag_text)
                    
                    i = end_tag + 1
            else:
                i += 1
        
        if tag_stack:
            # Some tags were not closed
            open_tags = ', '.join(f'<{tag}>' for tag in tag_stack)
            open_line, open_col = positions.get(0, (0, 0))
            return False, f"Unclosed tags: {open_tags} starting at line {open_line}, column {open_col}"
        
        return True, None
    
    except Exception as e:
        return False, f"XML validation error: {str(e)}"

def validate_attributes(attrs_text: str) -> bool:
    """Validate attribute syntax in an XML tag.
    
    Args:
        attrs_text: The attribute portion of a tag
        
    Returns:
        True if attributes are valid, raises exception otherwise
    """
    # Remove trailing slash for self-closing tags
    attrs_text = attrs_text.strip()
    if attrs_text.endswith('/'):
        attrs_text = attrs_text[:-1].strip()
    
    # Simple regex to match attribute patterns
    # name="value" or name='value' or name=value
    attr_pattern = r'([a-zA-Z0-9_:-]+)\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]*))'
    
    # Find all attributes in the text
    pos = 0
    while pos < len(attrs_text):
        # Skip whitespace
        while pos < len(attrs_text) and attrs_text[pos].isspace():
            pos += 1
        
        if pos >= len(attrs_text):
            break
            
        # Find the attribute name
        name_start = pos
        while pos < len(attrs_text) and attrs_text[pos] not in '= \t\n\r':
            pos += 1
            
        if pos >= len(attrs_text):
            raise ValueError(f"Attribute name not followed by '=' in '{attrs_text}'")
            
        name = attrs_text[name_start:pos].strip()
        if not name:
            raise ValueError(f"Empty attribute name in '{attrs_text}'")
            
        # Skip whitespace before =
        while pos < len(attrs_text) and attrs_text[pos].isspace():
            pos += 1
            
        if pos >= len(attrs_text) or attrs_text[pos] != '=':
            raise ValueError(f"Attribute '{name}' not followed by '='")
            
        pos += 1 # Skip the =
        
        # Skip whitespace after =
        while pos < len(attrs_text) and attrs_text[pos].isspace():
            pos += 1
            
        if pos >= len(attrs_text):
            raise ValueError(f"Attribute '{name}' has no value")
            
        # Check for quoted or unquoted value
        if attrs_text[pos] in '"\'':
            # Quoted value
            quote = attrs_text[pos]
            pos += 1
            value_start = pos
            while pos < len(attrs_text) and attrs_text[pos] != quote:
                pos += 1
                
            if pos >= len(attrs_text):
                raise ValueError(f"Unterminated quoted value for attribute '{name}'")
                
            # Skip the closing quote
            pos += 1
        else:
            # Unquoted value
            value_start = pos
            while pos < len(attrs_text) and not attrs_text[pos].isspace():
                pos += 1
    
    return True

def parse_xml_preview(xml_string: str, repo_path: str) -> List[Dict[str, Any]]:
    """Parse XML and generate preview of changes without applying them.
    
    This function is similar to parse_xml but instead of applying changes,
    it generates a preview of what would be changed.
    
    Args:
        xml_string: XML string containing file changes
        repo_path: Path to the repository
        
    Returns:
        List of dictionaries with preview information
    """
    try:
        # Parse the XML string to get file changes
        parsed_changes = parse_xml_string(xml_string)
        
        # Validate that we have valid FileChange objects
        if not parsed_changes:
            raise XMLParserError("No valid changes found in XML")
        
        # Ensure all items are valid FileChange objects
        valid_changes = []
        for i, change in enumerate(parsed_changes):
            if not isinstance(change, FileChange):
                logger.warning(f"Skipping invalid object at position {i}: {type(change)}")
                continue
            valid_changes.append(change)
        
        if not valid_changes:
            raise XMLParserError("No valid FileChange objects found after filtering")
        
        # Generate previews
        previews = []
        
        for change in valid_changes:
            preview = {"path": change.path, "operation": change.operation}
            
            # Add summary if available
            if change.summary:
                preview["summary"] = change.summary
                
            # Get absolute path
            file_path = os.path.join(repo_path, change.path)
            
            # Handle different operations
            if change.operation == "CREATE":
                preview["operation_desc"] = "Creating new file"
                preview["file_exists"] = os.path.exists(file_path)
                
                # Include preview of content
                if change.code:
                    # Limit content preview to avoid overwhelming UI
                    content_preview = change.code if len(change.code) <= 1000 else change.code[:1000] + "... (truncated)"
                    preview["content"] = content_preview
                else:
                    preview["content"] = ""
                    
            elif change.operation == "UPDATE":
                preview["operation_desc"] = "Updating existing file"
                preview["file_exists"] = os.path.exists(file_path)
                
                # Include content preview
                if change.code:
                    # Limit content preview to avoid overwhelming UI
                    content_preview = change.code if len(change.code) <= 1000 else change.code[:1000] + "... (truncated)"
                    preview["content"] = content_preview
                else:
                    preview["content"] = ""
                    
                # Warn if file doesn't exist (this is a potential error)
                if not os.path.exists(file_path):
                    preview["warning"] = "File doesn't exist but operation is UPDATE"
                    
            elif change.operation == "DELETE":
                preview["operation_desc"] = "Deleting file"
                preview["file_exists"] = os.path.exists(file_path)
                
                # Warn if file doesn't exist (this is a potential error)
                if not os.path.exists(file_path):
                    preview["warning"] = "File doesn't exist but operation is DELETE"
                    
            elif change.operation == "MODIFY":
                preview["operation_desc"] = "Modifying specific parts of file"
                preview["file_exists"] = os.path.exists(file_path)
                
                if not os.path.exists(file_path):
                    preview["warning"] = "File doesn't exist but operation is MODIFY"
                    continue
                    
                # Search for matches and add match count
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        file_content = f.read()
                    
                    # Determine if we're using regex or direct matching
                    if change.search:
                        # Try to find all matches
                        matches = find_all_matches(change.search, file_content)
                        preview["match_count"] = len(matches)
                        
                        if len(matches) > 0:
                            # Show preview of first match and replacement
                            first_match = matches[0]
                            preview["match_preview"] = first_match
                            
                            if change.code:
                                # Show what the replacement would look like
                                preview["replacement"] = change.code
                        else:
                            preview["warning"] = "No matches found for search pattern"
                    else:
                        preview["warning"] = "No search pattern provided for MODIFY operation"
                except Exception as e:
                    preview["error"] = f"Error reading file: {str(e)}"
            else:
                # Unknown operation
                preview["operation_desc"] = f"Unknown operation: {change.operation}"
                preview["warning"] = f"Unrecognized operation: {change.operation}"
            
            # Add to the previews list
            previews.append(preview)
            
        return previews
    except XMLParserError as e:
        # Re-wrap the error with preview-specific context
        logger.error(f"Error previewing changes: {str(e)}")
        raise XMLParserError(f"Error previewing changes: {str(e)}")
    except Exception as e:
        # Handle all other exceptions
        logger.error(f"Error previewing changes: {str(e)}")
        raise XMLParserError(f"Error previewing changes: {str(e)}")

def parse_xml(xml_string: str, repo_path: str, lenient_search: bool = False) -> bool:
    """Parse an XML string and apply the changes to the repository.
    
    This function parses the XML string, extracts file changes,
    and applies them to the repository.
    
    Args:
        xml_string: XML string containing file changes
        repo_path: Path to the repository
        
    Returns:
        True if changes were applied successfully, False otherwise
    """
    # Track success of individual changes
    all_changes_successful = True
    applied_changes = []
    failed_changes = []
    
    try:
        # Decode XML entities if needed
        xml_string = decode_xml_entities(xml_string)
        
        # Validate XML structure
        is_valid, error_message = validate_xml_structure(xml_string)
        if not is_valid:
            logger.warning(f"XML validation warning: {error_message}")
            # Continue anyway, we'll try to parse what we can
        
        # Parse the XML to get file changes
        changes = parse_xml_string(xml_string)
        
        if not changes:
            logger.error("No valid changes found in XML")
            return False
            
        # Ensure all changes are FileChange objects
        valid_changes = []
        for i, change in enumerate(changes):
            if not isinstance(change, FileChange):
                logger.warning(f"Item at position {i} is not a FileChange object: {type(change)}")
                continue
            valid_changes.append(change)
        
        if not valid_changes:
            logger.error("No valid FileChange objects found after filtering")
            return False
            
        # Process changes one by one, allowing partial success
        for change in valid_changes:
            try:
                # Log the change being processed
                logger.info(f"Processing {change.operation} for {change.path}")
                
                # Apply the change based on operation type
                if change.operation == "CREATE":
                    success = create_file(repo_path, change.path, change.code)
                elif change.operation == "UPDATE":
                    success = update_file(repo_path, change.path, change.code)
                elif change.operation == "DELETE":
                    success = delete_file(repo_path, change.path)
                elif change.operation == "MODIFY":
                    success = modify_file(repo_path, change.path, change.search, change.code)
                else:
                    logger.error(f"Unknown operation: {change.operation}")
                    failed_changes.append(change)
                    all_changes_successful = False
                    continue
                    
                # Track success or failure
                if success:
                    applied_changes.append(change)
                    logger.info(f"Successfully applied {change.operation} to {change.path}")
                else:
                    failed_changes.append(change)
                    all_changes_successful = False
                    logger.error(f"Failed to apply {change.operation} to {change.path}")
                    
            except Exception as e:
                failed_changes.append(change)
                all_changes_successful = False
                logger.error(f"Error applying {change.operation} to {change.path}: {str(e)}")
                
        # Log summary of changes
        logger.info(f"Applied {len(applied_changes)} changes successfully")
        if failed_changes:
            logger.warning(f"Failed to apply {len(failed_changes)} changes")
            
        return all_changes_successful
        
    except XMLParserError as e:
        logger.error(f"XML parsing error: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Error applying changes: {str(e)}")
        return False


def decode_xml_entities(xml_string: str) -> str:
    """Decode XML entities in the string.
    
    This function handles common XML entities and converts them to their
    corresponding characters.
    
    Args:
        xml_string: The XML string that may contain entities
        
    Returns:
        The XML string with entities decoded
    """
    # Define common XML entities and their replacements
    entities = {
        '&lt;': '<',
        '&gt;': '>',
        '&amp;': '&',
        '&quot;': '"',
        '&apos;': "'",
        '&#39;': "'",
        '&#34;': '"',
        '&#x27;': "'",
        '&#x22;': '"',
        '&nbsp;': ' ',
    }
    
    # Replace each entity with its corresponding character
    for entity, char in entities.items():
        xml_string = xml_string.replace(entity, char)
    
    # Handle numeric entities with a regex
    def replace_numeric_entity(match):
        code = match.group(1)
        try:
            if code.startswith('x'):
                # Hexadecimal entity
                return chr(int(code[1:], 16))
            else:
                # Decimal entity
                return chr(int(code))
        except (ValueError, OverflowError):
            # If conversion fails, return the original entity
            return match.group(0)
    
    # Replace both decimal (&#123;) and hex (&#x1F;) entities
    xml_string = re.sub(r'&#(x[0-9a-fA-F]+|[0-9]+);', replace_numeric_entity, xml_string)
    
    return xml_string

def find_all_matches(search_pattern: str, file_content: str) -> List[str]:
    """Find all occurrences of a search pattern in file content.
    
    Args:
        search_pattern: The pattern to search for
        file_content: The content to search in
        
    Returns:
        List of matching strings found in the content
    """
    if not search_pattern or not file_content:
        return []
        
    # First try direct matching (most common case)
    direct_matches = []
    start_idx = 0
    while True:
        idx = file_content.find(search_pattern, start_idx)
        if idx == -1:
            break
        direct_matches.append(search_pattern)
        start_idx = idx + len(search_pattern)
    
    if direct_matches:
        return direct_matches
        
    # If no direct matches, try with normalized whitespace
    normalized_search = normalize_whitespace(search_pattern, preserve_structure=True)
    normalized_content = normalize_whitespace(file_content, preserve_structure=True)
    
    fuzzy_matches = []
    lines = file_content.splitlines()
    search_lines = search_pattern.splitlines()
    
    # Sliding window approach to find matches
    if len(search_lines) <= len(lines):
        for i in range(len(lines) - len(search_lines) + 1):
            window = lines[i:i + len(search_lines)]
            window_text = '\n'.join(window)
            ratio = difflib.SequenceMatcher(None, search_pattern, window_text).ratio()
            
            if ratio > 0.8:  # Good match
                fuzzy_matches.append(window_text)
    
    return fuzzy_matches

def create_file(repo_path: str, relative_path: str, content: Optional[str] = None) -> bool:
    """Create a new file in the repository.
    
    Args:
        repo_path: The root path of the repository
        relative_path: The path to the file relative to repo_path
        content: The content to write to the file
        
    Returns:
        True if the file was created successfully, False otherwise
    """
    try:
        # Build the full path
        full_path = os.path.join(repo_path, relative_path)
        
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Write the file content
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content or "")
            
        logger.info(f"Created file: {relative_path}")
        return True
    except Exception as e:
        logger.error(f"Error creating file {relative_path}: {str(e)}")
        return False

def update_file(repo_path: str, relative_path: str, content: Optional[str] = None) -> bool:
    """Update (overwrite) an existing file in the repository.
    
    Args:
        repo_path: The root path of the repository
        relative_path: The path to the file relative to repo_path
        content: The new content for the file
        
    Returns:
        True if the file was updated successfully, False otherwise
    """
    try:
        # Build the full path
        full_path = os.path.join(repo_path, relative_path)
        
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Write the file content (overwriting any existing content)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content or "")
            
        logger.info(f"Updated file: {relative_path}")
        return True
    except Exception as e:
        logger.error(f"Error updating file {relative_path}: {str(e)}")
        return False

def delete_file(repo_path: str, relative_path: str) -> bool:
    """Delete a file from the repository.
    
    Args:
        repo_path: The root path of the repository
        relative_path: The path to the file relative to repo_path
        
    Returns:
        True if the file was deleted successfully, False otherwise
    """
    try:
        # Build the full path
        full_path = os.path.join(repo_path, relative_path)
        
        # Check if the file exists
        if not os.path.exists(full_path):
            logger.warning(f"File does not exist: {relative_path}")
            return False
            
        # Delete the file
        os.remove(full_path)
        
        logger.info(f"Deleted file: {relative_path}")
        return True
    except Exception as e:
        logger.error(f"Error deleting file {relative_path}: {str(e)}")
        return False

def modify_file(repo_path: str, relative_path: str, search_pattern: str, 
             replacement: Optional[str] = None, lenient_search: bool = False) -> bool:
    """Modify parts of a file by replacing a search pattern with new content.
    
    Args:
        repo_path: The root path of the repository
        relative_path: The path to the file relative to repo_path
        search_pattern: The pattern to search for in the file
        replacement: The content to replace the search pattern with
        lenient_search: If True, missing search patterns are treated as warnings but not failures
        
    Returns:
        True if the file was modified successfully or if lenient_search is True and pattern not found
    """
    try:
        # Build the full path
        full_path = os.path.join(repo_path, relative_path)
        
        # Check if the file exists
        if not os.path.exists(full_path):
            logger.warning(f"File does not exist: {relative_path}")
            return False
            
        # Read the current file content
        with open(full_path, 'r', encoding='utf-8') as f:
            current_content = f.read()
            
        # Check if the search pattern exists in the content
        if search_pattern not in current_content:
            # Try to find a close match
            matched_text, match_ratio = find_closest_match(search_pattern, current_content)
            
            if matched_text and match_ratio >= 0.8:
                # Good match, proceed with replacement
                logger.debug(f"Found close match with ratio {match_ratio:.2f}")
                new_content = current_content.replace(matched_text, replacement or "")
            else:
                if lenient_search:
                    # With lenient_search, we log a warning but don't consider it a failure
                    logger.warning(f"Search pattern not found in file (treating as non-fatal): {relative_path}")
                    return True
                else:
                    # Without lenient_search, this is a failure
                    logger.warning(f"Search pattern not found in file: {relative_path}")
                    return False
        else:
            # Direct replacement
            new_content = current_content.replace(search_pattern, replacement or "")
            
        # Write the modified content back to the file
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
            
        logger.info(f"Modified file: {relative_path}")
        return True
    except Exception as e:
        logger.error(f"Error modifying file {relative_path}: {str(e)}")
        return False

def process_xml_changes(
    xml_content: str, 
    repo_path: Optional[str] = None,
    preview_only: bool = False,
    verbose: bool = False,
    lenient_search: bool = False
) -> Dict[str, Any]:
    """Process XML changes and apply them to a repository.
    
    This function provides a high-level API for processing XML-based repository
    changes. It can parse XML, generate previews of changes, and apply the changes
    to a repository.
    
    Args:
        xml_content: XML string describing the changes
        repo_path: Path to the repository (default: current directory)
        preview_only: If True, generate previews but don't apply changes
        verbose: If True, enable verbose logging
        lenient_search: If True, missing search patterns in MODIFY operations
                      are treated as warnings rather than failures
        
    Returns:
        Dictionary with results of the operation:
        {
            'success': bool,            # Whether the operation was successful
            'changes': List[FileChange], # Parsed changes (if parsing successful)
            'previews': List[Dict],     # Preview information (if requested)
            'applied': int,            # Number of changes applied (if not preview_only)
            'failed': int,             # Number of changes that failed (if not preview_only)
            'error': str               # Error message (if operation failed)
        }
    """
    # Set up result dictionary
    result = {
        'success': False,
        'changes': [],
        'previews': [],
        'applied': 0,
        'failed': 0,
        'error': None
    }
    
    # Set default repo path if not provided
    if repo_path is None:
        repo_path = os.getcwd()
    
    # Enable verbose logging if requested
    if verbose:
        logging.getLogger('repo_tools.modules.xml_parser').setLevel(logging.DEBUG)
    
    try:
        # Parse the XML to get changes
        changes = parse_xml_string(xml_content)
        
        if not changes:
            result['error'] = "No valid changes found in XML"
            return result
            
        # Store the parsed changes
        result['changes'] = changes
        
        # Generate previews if requested or if in preview-only mode
        if preview_only or verbose:
            try:
                previews = parse_xml_preview(xml_content, repo_path)
                result['previews'] = previews
            except Exception as e:
                logger.warning(f"Error generating previews: {str(e)}")
                # Continue with applying changes if not in preview-only mode
                if preview_only:
                    result['error'] = f"Error generating previews: {str(e)}"
                    return result
        
        # Apply changes if not in preview-only mode
        if not preview_only:
            # Apply the changes
            success = parse_xml(xml_content, repo_path, lenient_search)
            result['success'] = success
            
            # Count applied and failed changes (estimate based on success flag)
            if success:
                result['applied'] = len(changes)
                result['failed'] = 0
            else:
                # If we failed, assume some changes might have been applied
                # This is an estimate since we don't have precise tracking
                result['applied'] = 0
                result['failed'] = len(changes)
        else:
            # In preview-only mode, we consider the operation successful if we got this far
            result['success'] = True
            
        return result
            
    except XMLParserError as e:
        logger.error(f"XML parsing error: {str(e)}")
        result['error'] = str(e)
        return result
    except Exception as e:
        logger.error(f"Error processing XML changes: {str(e)}")
        result['error'] = str(e)
        return result

def generate_xml_from_changes(
    changes: List[Dict[str, Any]]
) -> str:
    """Generate XML from a list of change dictionaries.
    
    This function converts a list of change dictionaries to a properly
    formatted XML string that can be parsed by the XML parser.
    
    Args:
        changes: List of change dictionaries, each with keys:
                - path: Path to the file
                - operation: Operation (CREATE, UPDATE, DELETE, MODIFY)
                - code: Content for CREATE, UPDATE, or MODIFY operations (optional for DELETE)
                - search: Search pattern for MODIFY operations (required for MODIFY)
                - description: Description of the change (optional)
                
    Returns:
        XML string that can be processed by the XML parser
    """
    xml_parts = []
    
    for change in changes:
        path = change.get('path')
        operation = change.get('operation', 'UPDATE').upper()
        code = change.get('code', '')
        search = change.get('search', '')
        description = change.get('description', '')
        
        if not path:
            continue
            
        # Start file element
        xml_parts.append(f'<file path="{path}" action="{operation.lower()}">')
        
        if operation == 'MODIFY' and search:
            # Add change block for MODIFY operations
            xml_parts.append('  <change>')
            
            if description:
                xml_parts.append(f'    <description>{description}</description>')
                
            if search:
                xml_parts.append('    <search>')
                xml_parts.append('===')
                xml_parts.append(search)
                xml_parts.append('===')
                xml_parts.append('    </search>')
                
            if code:
                xml_parts.append('    <content>')
                xml_parts.append('===')
                xml_parts.append(code)
                xml_parts.append('===')
                xml_parts.append('    </content>')
                
            xml_parts.append('  </change>')
        elif operation != 'DELETE' and code:
            # Add direct content for CREATE and UPDATE operations
            xml_parts.append('  <content>')
            xml_parts.append(code)
            xml_parts.append('  </content>')
            
        # Close file element
        xml_parts.append('</file>')
        
    return '\n'.join(xml_parts)

def validate_changes(changes: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """Validate a list of change dictionaries.
    
    This function checks if the change dictionaries have the required fields
    for their respective operations.
    
    Args:
        changes: List of change dictionaries to validate
        
    Returns:
        Tuple of (is_valid, error_messages)
    """
    is_valid = True
    error_messages = []
    
    for i, change in enumerate(changes):
        path = change.get('path')
        operation = change.get('operation', 'UPDATE').upper()
        code = change.get('code', '')
        search = change.get('search', '')
        
        if not path:
            error_messages.append(f"Change {i+1}: Missing required 'path' field")
            is_valid = False
            continue
            
        if operation not in ['CREATE', 'UPDATE', 'DELETE', 'MODIFY']:
            error_messages.append(f"Change {i+1}: Invalid operation '{operation}'")
            is_valid = False
            
        if operation in ['CREATE', 'UPDATE'] and not code:
            error_messages.append(f"Change {i+1}: Missing required 'code' field for {operation} operation")
            is_valid = False
            
        if operation == 'MODIFY':
            if not search:
                error_messages.append(f"Change {i+1}: Missing required 'search' field for MODIFY operation")
                is_valid = False
            if not code:
                error_messages.append(f"Change {i+1}: Missing required 'code' field for MODIFY operation")
                is_valid = False
                
    return is_valid, error_messages

# Command-line interface for the XML parser
if __name__ == '__main__':
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description='Process XML-based repository changes')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--xml', help='XML string describing changes')
    group.add_argument('--file', help='Path to XML file describing changes')
    parser.add_argument('--repo-path', default=os.getcwd(), help='Path to repository (default: current directory)')
    parser.add_argument('--preview', action='store_true', help="Generate previews but don't apply changes")
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--json', action='store_true', help='Output results as JSON')
    parser.add_argument('--lenient-search', action='store_true', 
                        help='Treat missing search patterns as warnings rather than errors')
    parser.add_argument('--test', action='store_true', help='Run built-in tests')
    
    args = parser.parse_args()
    
    # Run built-in tests if requested
    if args.test:
        def test_parser():
            """Run tests for the XML parser with various formats."""
            print("Running XML parser tests...")
            
            test_cases = [
                # Test standard XML format
                {
                    "name": "Standard file with create action",
                    "xml": """<file path="path/to/example.swift" action="create">
  <change>
    <description>Create a new file</description>
    <content>
===
import Foundation
struct Example {
    let id: UUID
}
===
    </content>
  </change>
</file>""",
                    "expected_changes": 1
                },
                
                # Test XML with search and replace
                {
                    "name": "File with modify action and search/replace",
                    "xml": """<file path="Models/User.swift" action="modify">
  <change>
    <description>Add email property to User struct</description>
    <search>
===
struct User {
    let id: UUID
    var name: String
}
===
    </search>
    <content>
===
struct User {
    let id: UUID
    var name: String
    var email: String
}
===
    </content>
  </change>
</file>""",
                    "expected_changes": 1
                },
                
                # Test XML from user's example 
                {
                    "name": "XML format from user example",
                    "xml": """<Plan>
Add email property to `User` via search/replace.
</Plan>

<file path="Models/User.swift" action="modify">
  <change>
    <description>Add email property to User struct</description>
    <search>
===
struct User {
    let id: UUID
    var name: String
}
===
    </search>
    <content>
===
struct User {
    let id: UUID
    var name: String
    var email: String
}
===
    </content>
  </change>
</file>""",
                    "expected_changes": 1
                },
                
                # Test XML with multiple files
                {
                    "name": "XML with multiple file changes",
                    "xml": """<file path="Models/User.swift" action="modify">
  <change>
    <description>Add email property</description>
    <search>
===
struct User {
    let id: UUID
    var name: String
}
===
    </search>
    <content>
===
struct User {
    let id: UUID
    var name: String
    var email: String
}
===
    </content>
  </change>
</file>
<file path="Views/UserView.swift" action="create">
  <change>
    <description>Create user view</description>
    <content>
===
import SwiftUI
struct UserView: View {
    var body: some View {
        Text("User View")
    }
}
===
    </content>
  </change>
</file>""",
                    "expected_changes": 2
                },
                
                # Test XML without angle brackets (should fail gracefully)
                {
                    "name": "XML without angle brackets (error case)",
                    "xml": "This is not XML content",
                    "expected_error": "Invalid XML format: missing angle brackets"
                },
                
                # Test malformed XML that can be recovered
                {
                    "name": "Malformed XML that can be recovered",
                    "xml": """Some text before the XML
<file path="Models/User.swift" action="create">
  <content>
    struct User {
        let id: UUID
    }
  </content>
</file>""",
                    "expected_changes": 1
                },
                
                # Test XML with rewrite action
                {
                    "name": "File with rewrite action",
                    "xml": """<file path="Models/User.swift" action="rewrite">
  <change>
    <description>Full file rewrite with new email field</description>
    <content>
===
import Foundation
struct User {
    let id: UUID
    var name: String
    var email: String

    init(name: String, email: String) {
        self.id = UUID()
        self.name = name
        self.email = email
    }
}
===
    </content>
  </change>
</file>""",
                    "expected_changes": 1
                },
                
                # Test XML with delete action
                {
                    "name": "File with delete action",
                    "xml": """<file path="Obsolete/File.swift" action="delete">
  <change>
    <description>Completely remove the file from the project</description>
    <content>
===
===
    </content>
  </change>
</file>""",
                    "expected_changes": 1
                },
                
                # Test XML with xml_formatting_instructions tag (exact case from user)
                {
                    "name": "XML with formatting instructions tag",
                    "xml": """<xml_formatting_instructions>
### Role
- You are a **code editing assistant**: You can fulfill edit requests and chat with the user about code or other questions. Provide complete instructions or code lines when replying with xml formatting.

### Capabilities
- Can create new files.
- Can rewrite entire files.
- Can perform partial search/replace modifications.
- Can delete existing files.

Avoid placeholders like `...` or `// existing code here`. Provide complete lines or code.

## Tools & Actions
1. **create** – Create a new file if it doesn't exist.
2. **rewrite** – Replace the entire content of an existing file.
3. **modify** (search/replace) – For partial edits with <search> + <content>.
4. **delete** – Remove a file entirely (empty <content>).

### **Format to Follow for Repo Prompt's Diff Protocol**

<Plan>
Describe your approach or reasoning here.
</Plan>

<file path="path/to/example.swift" action="one_of_the_tools">
  <change>
    <description>Brief explanation of this specific change</description>
    <search>
===
// Exactly matching lines to find
===
    </search>
    <content>
===
// Provide the new or updated code here. Do not use placeholders
===
    </content>
  </change>
  <!-- Add more <change> blocks if you have multiple edits for the same file -->
</file>

#### Tools Demonstration
1. `<file path="NewFile.swift" action="create">` – Full file in <content>
2. `<file path="DeleteMe.swift" action="delete">` – Empty <content>
3. `<file path="ModifyMe.swift" action="modify">` – Partial edit with `<search>` + `<content>`
4. `<file path="RewriteMe.swift" action="rewrite">` – Entire file in <content>
5. `<file path="RewriteMe.swift" action="rewrite">` – Entire file in <content>. No <search> required.

## Format Guidelines
1. **Plan**: Begin with a `<Plan>` block explaining your approach.
2. **<file> Tag**: e.g. `<file path="Models/User.swift" action="...">`. Must match an available tool.
3. **<change> Tag**: Provide `<description>` to clarify each change. Then `<content>` for new/modified code. Additional rules depend on your capabilities.
4. **modify**: **<search> & <content>**: Provide code blocks enclosed by ===. Respect indentation exactly, ensuring the <search> block matches the original source down to braces, spacing, and any comments. The new <content> will replace the <search> block, and should should fit perfectly in the space left by it's removal.
5. **modify**: For changes to the same file, ensure that you use multiple change blocks, rather than separate file blocks.
6. **rewrite**: For large overhauls; omit `<search>` and put the entire file in `<content>`.
7. **create**: For new files, put the full file in <content>.
8. **delete**: Provide an empty <content>. The file is removed.

## Code Examples

-----
### Example: Search and Replace (Add email property)
<Plan>
Add an email property to `User` via search/replace.
</Plan>

<file path="Models/User.swift" action="modify">
  <change>
    <description>Add email property to User struct</description>
    <search>
===
struct User {
    let id: UUID
    var name: String
}
===
    </search>
    <content>
===
struct User {
    let id: UUID
    var name: String
    var email: String
}
===
    </content>
  </change>
</file>

-----
### Example: Negative Example - Mismatched Search Block
// Example Input (not part of final output, just demonstration)
<file_contents>
File: path/service.swift
```
import Foundation
class Example {
    foo() {
        Bar()
    }
}
```
</file_contents>

<Plan>
Demonstrate how a mismatched search block leads to failed merges.
</Plan>

<file path="path/service.swift" action="modify">
  <change>
    <description>This search block is missing or has mismatched indentation, braces, etc.</description>
    <search>
===
    foo() {
        Bar()
    }
===
    </search>
    <content>
===
    foo() {
        Bar()
        Bar2()
    }
===
    </content>
  </change>
</file>

<!-- This example fails because the <search> block doesn't exactly match the original file contents. -->

-----
### Example: Negative Example - Mismatched Brace Balance
// This negative example shows how adding extra braces in the <content> can break brace matching.
<Plan>
Demonstrate that the new content block has one extra closing brace, causing mismatched braces.
</Plan>

<file path="Functions/MismatchedBracesExample.swift" action="modify">
  <change>
    <description>Mismatched brace balance in the replacement content</description>
    <search>
===
    foo() {
        Bar()
    }
===
    </search>
    <content>
===
    foo() {
        Bar()
    }

    bar() {
        foo2()
    }
}
===
    </content>
  </change>
</file>

<!-- Because the <search> block was only a small brace segment, adding extra braces in <content> breaks the balance. -->

-----
### Example: Negative Example - One-Line Search Block
<Plan>
Demonstrate a one-line search block, which is too short to be reliable.
</Plan>

<file path="path/service.swift" action="modify">
  <change>
    <description>One-line search block is ambiguous</description>
    <search>
===
var email: String
===
    </search>
    <content>
===
var emailNew: String
===
    </content>
  </change>
</file>

<!-- This example fails because the <search> block is only one line and ambiguous. -->

-----
### Example: Negative Example - Ambiguous Search Block
<Plan>
Demonstrate an ambiguous search block that can match multiple blocks (e.g., multiple closing braces).
</Plan>

<file path="path/service.swift" action="modify">
  <change>
    <description>Ambiguous search block with multiple closing braces</description>
    <search>
===
    }
}
===
    </search>
    <content>
===
        foo() {
        }
    }
}
===
    </content>
  </change>
</file>

<!-- This example fails because the <search> block is ambiguous due to multiple matching closing braces. -->

-----
### Example: Full File Rewrite
<Plan>
Rewrite the entire User file to include an email property.
</Plan>

<file path="Models/User.swift" action="rewrite">
  <change>
    <description>Full file rewrite with new email field</description>
    <content>
===
import Foundation
struct User {
    let id: UUID
    var name: String
    var email: String

    init(name: String, email: String) {
        self.id = UUID()
        self.name = name
        self.email = email
    }
}
===
    </content>
  </change>
</file>

-----
### Example: Create New File
<Plan>
Create a new RoundedButton for a custom Swift UIButton subclass.
</Plan>

<file path="Views/RoundedButton.swift" action="create">
  <change>
    <description>Create custom RoundedButton class</description>
    <content>
===
import UIKit
@IBDesignable
class RoundedButton: UIButton {
    @IBInspectable var cornerRadius: CGFloat = 0
}
===
    </content>
  </change>
</file>

-----
### Example: Delete a File
<Plan>
Remove an obsolete file.
</Plan>

<file path="Obsolete/File.swift" action="delete">
  <change>
    <description>Completely remove the file from the project</description>
    <content>
===
===
    </content>
  </change>
</file>

## Final Notes
1. **modify** Always wrap the exact original lines in <search> and your updated lines in <content>, each enclosed by ===.
2. **modify** The <search> block must match the source code exactly—down to indentation, braces, spacing, and any comments. Even a minor mismatch causes failed merges.
3. **modify** Only replace exactly what you need. Avoid including entire functions or files if only a small snippet changes, and ensure the <search> content is unique and easy to identify.
4. **rewrite** Use `rewrite` for major overhauls, and `modify` for smaller, localized edits. Rewrite requires the entire code to be replaced, so use it sparingly.
5. You can always **create** new files and **delete** existing files. Provide full code for create, and empty content for delete. Avoid creating files you know exist already.
6. If a file tree is provided, place your files logically within that structure. Respect the user's relative or absolute paths.
7. Wrap your final output in ```XML ... ``` for clarity.
8. **Important:** Do not wrap any XML output in CDATA tags (i.e. `<![CDATA[ ... ]]>`). Repo Prompt expects raw XML exactly as shown in the examples.
9. **IMPORTANT** IF MAKING FILE CHANGES, YOU MUST USE THE AVAILABLE XML FORMATTING CAPABILITIES PROVIDED ABOVE - IT IS THE ONLY WAY FOR YOUR CHANGES TO BE APPLIED.
10. The final output must apply cleanly with no leftover syntax errors.
</xml_formatting_instructions>

<file path="Models/User.swift" action="modify">
  <change>
    <description>Add email property to User struct</description>
    <search>
===
struct User {
    let id: UUID
    var name: String
}
===
    </search>
    <content>
===
struct User {
    let id: UUID
    var name: String
    var email: String
}
===
    </content>
  </change>
</file>""",
                    "expected_changes": 1
                }
            ]
            
            # Run each test case
            test_results = []
            for i, test_case in enumerate(test_cases, 1):
                print(f"\nTest {i}: {test_case['name']}")
                try:
                    # Try to parse the XML
                    changes = parse_xml_string(test_case['xml'])
                    
                    # Check if we expected an error
                    if 'expected_error' in test_case:
                        test_results.append({
                            "name": test_case['name'],
                            "success": False,
                            "error": "Expected error but none occurred"
                        })
                        print(f"❌ Failed: Expected error '{test_case['expected_error']}' but none occurred")
                        continue
                    
                    # Check if we got the expected number of changes
                    if len(changes) != test_case.get('expected_changes', 0):
                        test_results.append({
                            "name": test_case['name'],
                            "success": False,
                            "error": f"Expected {test_case['expected_changes']} changes but got {len(changes)}"
                        })
                        print(f"❌ Failed: Expected {test_case['expected_changes']} changes but got {len(changes)}")
                        continue
                    
                    # Print summary of changes
                    print(f"✅ Parsed {len(changes)} changes successfully:")
                    for j, change in enumerate(changes, 1):
                        print(f"  {j}. {change.operation} {change.path}")
                        if change.operation == 'MODIFY':
                            print(f"     Search length: {len(change.search) if change.search else 0}")
                            print(f"     Content length: {len(change.code) if change.code else 0}")
                    
                    # Add success result
                    test_results.append({
                        "name": test_case['name'],
                        "success": True,
                        "changes": len(changes)
                    })
                    
                except Exception as e:
                    # Check if we expected this error
                    if 'expected_error' in test_case:
                        error_match = str(e) == test_case['expected_error']
                        test_results.append({
                            "name": test_case['name'],
                            "success": error_match,
                            "error": str(e),
                            "error_match": error_match
                        })
                        
                        if error_match:
                            print(f"✅ Got expected error: {str(e)}")
                        else:
                            print(f"❌ Expected error '{test_case['expected_error']}' but got: {str(e)}")
                    else:
                        test_results.append({
                            "name": test_case['name'],
                            "success": False,
                            "error": str(e)
                        })
                        print(f"❌ Failed with error: {str(e)}")
            
            # Print summary
            print("\nTest Summary:")
            successes = sum(1 for result in test_results if result['success'])
            print(f"✅ {successes}/{len(test_results)} tests passed")
            
            # Output detailed results if failures occurred
            if successes < len(test_results):
                print("\nFailed tests:")
                for result in test_results:
                    if not result['success']:
                        print(f"❌ {result['name']}: {result.get('error', 'Unknown error')}")
        
        # Run the tests
        test_parser()
        exit(0)
    
    # Get XML content
    xml_content = None
    if args.xml:
        xml_content = args.xml
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                xml_content = f.read()
        except Exception as e:
            print(f"Error reading file {args.file}: {str(e)}")
            exit(1)
    
    # Process the XML changes
    result = process_xml_changes(
        xml_content,
        repo_path=args.repo_path,
        preview_only=args.preview,
        verbose=args.verbose,
        lenient_search=args.lenient_search
    )
    
    # Output results
    if args.json:
        # Convert FileChange objects to dictionaries for JSON serialization
        if 'changes' in result:
            result['changes'] = [
                {
                    'path': change.path,
                    'operation': change.operation,
                    'summary': change.summary
                }
                for change in result['changes']
            ]
        print(json.dumps(result, indent=2))
    else:
        # Print human-readable output
        if result['success']:
            print("✅ XML changes processed successfully")
        else:
            print(f"❌ Error: {result['error']}")
            
        if result['changes']:
            print(f"\nParsed {len(result['changes'])} changes:")
            for i, change in enumerate(result['changes'], 1):
                print(f"  {i}. {change.operation} {change.path}")
                
        if result['previews']:
            print(f"\nGenerated {len(result['previews'])} previews")
            
        if not args.preview:
            print(f"\nApplied {result['applied']} changes, failed {result['failed']} changes")