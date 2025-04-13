#!/usr/bin/env python3

"""
Test script for XML parser.

Usage:
  python test_xml_parser.py [--repo-path PATH]
  python test_xml_parser.py <xml_string> [--repo-path PATH]
  python test_xml_parser.py --file <xml_file> [--repo-path PATH]

Examples:
  python test_xml_parser.py  # Run all tests with default XML
  python test_xml_parser.py '<file path="test.txt" action="create"><content>Test content</content></file>'
  python test_xml_parser.py --file my_xml_changes.xml
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('xml_parser_test')

# Add parent directory to path to allow importing modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Import XML parser module
from repo_tools.modules.xml_parser import (
    parse_xml_string, 
    parse_xml_preview, 
    XMLParserError,
    validate_xml_structure
)

def test_path_prefix_stripping(repo_path):
    """Test that redundant path prefixes are correctly stripped."""
    print("\n=== PATH PREFIX STRIPPING TEST ===")
    
    # Get the current directory name (should be 'repo-tools' based on your description)
    current_dir = os.path.basename(os.path.abspath(repo_path))
    
    # Test XML with a path that includes redundant prefix
    xml_with_redundant_prefix = f'<file path="{current_dir}/package.json" action="update"><content>Test content</content></file>'
    
    try:
        changes = parse_xml_string(xml_with_redundant_prefix)
        
        # Check if the path was properly stripped
        if changes and changes[0].path == "package.json":
            print(f"✅ Successfully stripped redundant prefix '{current_dir}/' from path")
        else:
            actual_path = changes[0].path if changes else "No changes found"
            print(f"❌ Failed to strip redundant prefix. Expected 'package.json', got '{actual_path}'")
            
        # Additional check: verify the path with redundant prefix would not exist
        redundant_path = os.path.join(repo_path, f"{current_dir}/{current_dir}")
        if os.path.exists(redundant_path):
            print(f"⚠️ Warning: Path with double prefix actually exists: {redundant_path}")
        else:
            print(f"✅ Verified that path with double prefix does not exist: {redundant_path}")
            
    except Exception as e:
        print(f"❌ Error testing path prefix stripping: {str(e)}")

def test_parser(xml_string, repo_path=None):
    """Test parsing XML string and print results."""
    print("\n=== XML VALIDATION ===")
    is_valid, error_message = validate_xml_structure(xml_string)
    if is_valid:
        print("✅ XML structure is valid")
    else:
        print(f"⚠️ XML structure validation: {error_message}")
        print("(Will attempt to parse anyway)")
    
    print("\n=== PARSING RESULTS ===")
    try:
        changes = parse_xml_string(xml_string)
        print(f"✅ Successfully parsed {len(changes)} changes:")
        for i, change in enumerate(changes, 1):
            print(f"\n--- Change {i} ---")
            print(f"Operation: {change.operation}")
            print(f"Path: {change.path}")
            if change.summary:
                print(f"Summary: {change.summary}")
            if change.search:
                print(f"Search pattern: {change.search[:100]}..." if len(change.search) > 100 else f"Search pattern: {change.search}")
            if change.code:
                print(f"Content: {change.code[:100]}..." if len(change.code) > 100 else f"Content: {change.code}")
        
        if repo_path:
            print("\n=== PREVIEW RESULTS ===")
            try:
                previews = parse_xml_preview(xml_string, repo_path)
                print(f"✅ Successfully generated {len(previews)} previews:")
                for i, preview in enumerate(previews, 1):
                    print(f"\n--- Preview {i} ---")
                    for key, value in preview.items():
                        if isinstance(value, str) and len(value) > 100:
                            print(f"{key}: {value[:100]}...")
                        else:
                            print(f"{key}: {value}")
            except Exception as e:
                print(f"❌ Error generating previews: {str(e)}")
                
    except XMLParserError as e:
        print(f"❌ XML parsing error: {str(e)}")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()

def main():
    """Parse arguments and run test."""
    parser = argparse.ArgumentParser(description='Test XML Parser')
    parser.add_argument('xml_string', nargs='?', help='XML string to parse')
    parser.add_argument('--file', '-f', help='Path to XML file to parse')
    parser.add_argument('--repo-path', '-r', default=os.getcwd(),
                       help='Path to repository (default: current directory)')
    parser.add_argument('--debug', '-d', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('xml_parser').setLevel(logging.DEBUG)
    
    # First always run the path prefix test
    test_path_prefix_stripping(args.repo_path)
    
    # Get XML string from file or command line or use default
    xml_string = None
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                xml_string = f.read()
        except Exception as e:
            print(f"Error reading file {args.file}: {str(e)}")
            sys.exit(1)
    elif args.xml_string:
        xml_string = args.xml_string
    else:
        # Default XML for testing when none provided
        xml_string = '<file path="test.txt" action="create"><content>Test content for XML parser tests</content></file>'
        print("\n=== USING DEFAULT TEST XML ===")
        print(f"XML: {xml_string}")
    
    # Run the normal test with actual or default XML
    test_parser(xml_string, args.repo_path)

if __name__ == '__main__':
    main()