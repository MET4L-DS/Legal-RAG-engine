import re
import os

def normalize_text(text):
    # Remove page markers
    text = re.sub(r'## Page \d+\n?', '', text)
    text = re.sub(r'<page_number>\d+</page_number>\n?', '', text)
    text = re.sub(r'&lt;page_number&gt;\d+&lt;/page_number&gt;\n?', '', text)
    text = re.sub(r'---\n?', '', text)
    
    # Remove extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def parse_chapters(content):
    # Matches "CHAPTER [ROMAN]" at start of line, followed by title on next line(s)
    chapter_pattern = re.compile(r'(?:\n|^)\s*(?:\*\*)?(CHAPTER\s+[IVXLCDM]+)(?:\*\*)?\s*[\r\n]+\s*(.*)', re.MULTILINE)
    
    chapters = []
    matches = list(chapter_pattern.finditer(content))
    
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(content)
        
        chapter_id = match.group(1).strip()
        chapter_title = match.group(2).strip().strip('* ')
        chapter_content = content[match.end():end].strip()
        
        chapters.append({
            'id': chapter_id,
            'title': chapter_title,
            'content': chapter_content
        })
    
    return chapters

def format_section_blocks(content, expected_next_num):
    # Normalize section headers: **1. Title.**— -> [SEC] 1. 
    # Regex handles: **1. Title.**— or 1. Title
    content = re.sub(r'(?:\n|^)\s*(?:\*\*)?(\d+)\.\s+', r'\n[SEC] \1. ', content)
    
    parts = re.split(r'\n\[SEC\] (\d+)\.\s+', content)
    formatted = []
    
    if parts[0].strip():
        pre_text = parts[0].strip()
        pre_text = re.sub(r'(^[A-Z]\.—[^\n]+)$', r'**\1**\n', pre_text, flags=re.MULTILINE)
        formatted.append(pre_text + "\n\n")
        
    last_sec_num = expected_next_num - 1
    
    for i in range(1, len(parts), 2):
        orig_num = int(parts[i])
        sec_content = parts[i+1].strip()
        
        if orig_num < last_sec_num and orig_num <= 10:
            sec_num = last_sec_num + 1
        else:
            sec_num = orig_num
        last_sec_num = sec_num
        
        # Check for sub-chapter headings inside section content (rare but possible)
        next_extra = ""
        sub_ch_match = re.search(r'\n\s*(\*?\*?[A-Z]\.—[^\n]+\*?\*?)\s*$', sec_content)
        if sub_ch_match:
            next_extra = sub_ch_match.group(1).strip('* ')
            sec_content = sec_content[:sub_ch_match.start()].strip()
            
        # Title extraction: **Title.**—
        title = "Untitled"
        # Match title: can include stars, up to a dash or dot-space/dot-paren
        # BNS style: **1. Short title...**— (Number removed by split) -> Short title...**—
        # The regex split removed "1. ". The rest is "Short title...**—"
        
        # Extract title from start
        # Look for end of title marker: .**— or .— or —
        title_match = re.search(r'^([^\n—]+?)(?:\s*\.?\*?\*?\s*[—\-]+|\s*\.\s*\n|\s*\.\s+|$)', sec_content)
        
        if title_match:
            title = title_match.group(1).strip().strip('* ')
            sec_content = sec_content[title_match.end():].strip()
        else:
            lines = sec_content.split('\n')
            title = lines[0].strip().strip('* ')
            sec_content = "\n".join(lines[1:]).strip()
            
        formatted.append(f"## Section {sec_num} — {title}\n\n")
        
        # PRE-PROCESS CONTENT: Splitting logic
        
        def safe_split(text, pattern):
            return re.sub(r'(?:^|(?<=[\.\;\:\n]))\s*(' + pattern + r')', r'\n\1', text)

        sec_content = safe_split(sec_content, r'\(\d+\)')
        # Identify Roman Numeral candidates for splitting.
        # We invoke safe_split on (ii), (iii) etc.
        sec_content = safe_split(sec_content, r'\((?:ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)\)')
        # Also split (i) - treating it as potential start of line
        sec_content = safe_split(sec_content, r'\([a-z]\)') 
        
        # Formatting specific keywords
        sec_content = re.sub(r'(Provided\s+that)', r'\n\n\1', sec_content)
        # We rely on BNS source having Explanations/Illustrations on new lines
        # sec_content = safe_split(sec_content, r'Explanation\s*[\d\.]*[\.—]')
        # sec_content = safe_split(sec_content, r'Illustration\s*[\d\.]*[\.—]?')
        
        lines = sec_content.split('\n')
        formatted_lines = []
        is_definitions = "Definitions" in title
        
        # Context State
        last_clause_letter = None
        
        for line in lines:
            line = line.strip().strip('_')
            if not line: continue
            
            # Sub-sections (1), (2)
            sub_m = re.match(r'^(\(\d+\))(.*)', line)
            if sub_m:
                formatted_lines.append(f"**{sub_m.group(1)}** {sub_m.group(2).strip()}\n")
                last_clause_letter = None # Reset context
                continue

            # Roman Numerals vs Clauses Logic
            # Roman numerals: (i), (ii), ... (xii)
            # Clauses: (a), (b) ... (z)
            # Ambiguous: (i), (v), (x)
            
            roman_m = re.match(r'^(\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)\))(.*)', line)
            is_roman_line = False
            
            if roman_m:
                marker_raw = roman_m.group(1).strip("()")
                # Check for ambiguity
                is_ambiguous = marker_raw in ['i', 'v', 'x']
                
                is_roman = True
                if is_ambiguous:
                    # Context Check
                    # If we are expecting 'i' after 'h', 'v' after 'u', 'x' after 'w' -> It's a clause
                    precedent_map = {'i': 'h', 'v': 'u', 'x': 'w'}
                    precedent = precedent_map.get(marker_raw)
                    
                    if last_clause_letter == precedent:
                        is_roman = False
                    else:
                        is_roman = True
                
                if is_roman:
                    upper_marker = f"({marker_raw.upper()})"
                    formatted_lines.append(f"    - **{upper_marker}** {roman_m.group(2).strip()}\n")
                    is_roman_line = True
                    # Do NOT update last_clause_letter for roman lines (unless they interrupt clause flow? No, subclauses don't break clause alphabetic sequence strictly, but usually they are nested)
            
            if is_roman_line:
                continue

            # Clauses (a), (b)
            cl_m = re.match(r'^(\([a-z]\))(.*)', line)
            if cl_m:
                c_id = cl_m.group(1)
                c_text = cl_m.group(2).strip()
                if is_definitions:
                    # Italicize defined term "word"
                    c_text = re.sub(r'["“]([^"”]+)["”]', r'_“\1”_', c_text, count=1)
                
                formatted_lines.append(f"- **{c_id}** {c_text}\n")
                last_clause_letter = c_id.strip("()")
                continue
                
            # Uppercase Roman (if any exist in source)
            sc_m = re.match(r'^(\([IVXLCDM]+\))(.*)', line)
            if sc_m:
                formatted_lines.append(f"    - **{sc_m.group(1)}** {sc_m.group(2).strip()}\n")
                continue
                
            # Formatting Explanations/Illustrations
            # Handle "Explanation.—" or "Explanation 1.—"
            # Require separator . or — to avoid matching sentences starting/ending with keyword
            if line.startswith("Explanation") or line.startswith("Illustration"):
                 label_match = re.match(r'^(Explanation\s*\d*\s*[\.—]|Illustration\s*\d*\s*[\.—])(.*)', line)
                 if label_match:
                     label = label_match.group(1).strip().strip(".-—") + ".—" # Ensure standard ending
                     content_after = label_match.group(2).strip().strip("— -")
                     formatted_lines.append(f"**{label}**\n{content_after}\n")
                     continue
            
            formatted_lines.append(f"{line}\n")
            
        formatted.append("\n".join(formatted_lines))
        formatted.append("\n---\n\n")
        
        if next_extra:
            formatted.append(f"**{next_extra}**\n\n")
            
    res = "".join(formatted)
    return res, last_sec_num + 1

def process_bns(input_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    content = normalize_text(content)
    
    chapters = parse_chapters(content)
    print(f"Total Chapters Found: {len(chapters)}")
    
    global_sec_num = 1
    
    for chapter in chapters:
        chapter_id = chapter['id']
        chapter_title = chapter['title']
        
        # Clean title for filename
        clean_title = chapter_title.lower()
        clean_title = re.sub(r'[^a-z0-9]+', '_', clean_title).strip('_')
        
        roman_num = chapter_id.split(' ')[1].lower()
        filename = f"chapter_{roman_num}_{clean_title}.md"
        filepath = os.path.join(output_dir, filename)
        
        formatted_content = f"# {chapter_id}\n\n## {chapter_title}\n\n---\n\n"
        sec_formatted, next_sec_num = format_section_blocks(chapter['content'], global_sec_num)
        formatted_content += sec_formatted
        global_sec_num = next_sec_num
        
        # Final whitespace cleanup
        formatted_content = re.sub(r'\n{4,}', '\n\n', formatted_content)
        formatted_content = formatted_content.strip()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(formatted_content)
        print(f"Generated: {filename} (Sections up to {global_sec_num - 1})")

if __name__ == "__main__":
    input_file = r'c:\Met4l.DSCode\Python\Embedding-Test-Py\documents\bns.md'
    output_folder = r'c:\Met4l.DSCode\Python\Embedding-Test-Py\documents\BNS'
    process_bns(input_file, output_folder)
