#!/usr/bin/env python3
"""
Test script for XML parser.

Usage:
  python test_xml_parser.py <xml_string> [--repo-path PATH]
  python test_xml_parser.py --file <xml_file> [--repo-path PATH]

Examples:
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
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('xml_string', nargs='?', help='XML string to parse')
    group.add_argument('--file', '-f', help='Path to XML file to parse')
    parser.add_argument('--repo-path', '-r', default=os.getcwd(),
                       help='Path to repository (default: current directory)')
    parser.add_argument('--debug', '-d', action='store_true',
                       help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger('xml_parser').setLevel(logging.DEBUG)
    
    # Get XML string from file or command line
    xml_string = None
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                xml_string = f.read()
        except Exception as e:
            print(f"Error reading file {args.file}: {str(e)}")
            sys.exit(1)
    else:
        xml_string = args.xml_string
    
    # Run the test
    test_parser(xml_string, args.repo_path)

if __name__ == '__main__':
    main() 