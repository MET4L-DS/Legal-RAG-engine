import re
import os
import shutil

def convert_roman_numerals(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Regex for lowercase Roman numerals at start of line
    # We cover up to 20 (xx) just in case
    romans_set = {
        'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x', 
        'xi', 'xii', 'xiii', 'xiv', 'xv', 'xvi', 'xvii', 'xviii', 'xix', 'xx'
    }
    
    # Ambiguous ones that could be letters
    ambiguous = {'i', 'v', 'x'}
    
    # Predecessors that indicate LETTER usage
    # h -> i
    # u -> v
    # w -> x
    letter_predecessors = {
        'i': 'h',
        'v': 'u',
        'x': 'w'
    }

    new_lines = []
    
    # State tracking
    last_marker = None
    
    for line in lines:
        # Detect Header or Separator to reset state
        if line.startswith('##') or line.startswith('---'):
            last_marker = None
            new_lines.append(line)
            continue
            
        # Regex to find list marker: (xyz) at start of line (allowing whitespace)
        # Capture the content inside parens
        match = re.match(r'^(\s*)\(([a-z]+)\)(.*)', line)
        
        if match:
            indent = match.group(1)
            marker = match.group(2)
            rest = match.group(3)
            
            is_roman = False
            
            if marker in romans_set:
                if marker in ambiguous:
                    # Check context
                    if last_marker == letter_predecessors[marker]:
                        # It is a letter sequence (e.g. h -> i)
                        is_roman = False
                    else:
                        # Default to Roman (e.g. start of list, or following Roman)
                        is_roman = True
                else:
                    # It is definitely Roman (ii, iii, etc.)
                    is_roman = True
            
            # Update last_marker for next iteration
            last_marker = marker
            
            if is_roman:
                # Transform to uppercase
                upper_marker = marker.upper()
                new_line = f"{indent}({upper_marker}){rest}\n"
                new_lines.append(new_line)
            else:
                new_lines.append(line)
                
        else:
            # If line is not a list item, do we reset last_marker?
            # BNSS formatting often has multi-line text between list items.
            # We probably should NOT reset last_marker on simple text lines, 
            # only on explicit structure breaks (headers).
            # But what if 'h' is followed by a long paragraph, then 'i'? It's still a letter.
            new_lines.append(line)

    # Backup original
    shutil.copy(file_path, file_path + ".bak")
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print(f"Processed {len(lines)} lines.")

if __name__ == "__main__":
    target_file = r"c:\Met4l.DSCode\Python\Embedding-Test-Py\documents\BNSS\bnss.md"
    convert_roman_numerals(target_file)
