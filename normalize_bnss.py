import re
import os

def normalize_text(text):
    # Remove page markers
    text = re.sub(r'## Page \d+\n?', '', text)
    text = re.sub(r'<page_number>\d+</page_number>\n?', '', text)
    text = re.sub(r'---\n?', '', text)
    
    # Remove extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def parse_chapters(content):
    # Matches "CHAPTER [ROMAN]" at start of line, followed by title on next line(s)
    # Handles potential markdown like **CHAPTER V**
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
    # Normalize section headers
    content = re.sub(r'(?:\n|^)\s*(?:\*\*)?(\d+)\.\s*(?:\*\*)?', r'\n[SEC] \1. ', content)
    
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
        
        # Check for sub-chapter headings
        next_extra = ""
        sub_ch_match = re.search(r'\n\s*(\*?\*?[A-Z]\.—[^\n]+\*?\*?)\s*$', sec_content)
        if sub_ch_match:
            next_extra = sub_ch_match.group(1).strip('* ')
            sec_content = sec_content[:sub_ch_match.start()].strip()
            
        # Improved Title extraction
        title = "Untitled"
        # Match title: can include stars, up to a dash or dot-space/dot-paren
        title_match = re.search(r'^([^\n—]+?)(?:\s*\.?\*?\*?\s*[—\-]+|\s*\.\s+\(|\s*\.\s*\n|\s*\.\s+|$)', sec_content)
        if title_match:
            title = title_match.group(1).strip().strip('* ')
            sec_content = sec_content[title_match.end():].strip()
            if not sec_content.startswith('('):
                # If we cut off the separator but it wasn't a paren, check if we need to put back the start of a paren
                # Actually re-scan for first (n)
                pass
        else:
            lines = sec_content.split('\n')
            title = lines[0].strip().strip('* ')
            sec_content = "\n".join(lines[1:]).strip()
            
        formatted.append(f"## Section {sec_num} — {title}\n\n")
        
        # PRE-PROCESS CONTENT: Split concatenated (1)(2) or (a)(b) or (1)(a) onto new lines
        # ONLY split if preceded by newline, start of string, or sentence-ending punctuation/semicolons.
        # This prevents splitting "sub-sections (7), (8) and (9)"
        
        # Helper to safely insert newline
        def safe_split(text, pattern):
            # Split if preceded by: start of string, newline, dot, semicolon, or colon
            # \s* matches the whitespace that we will effectively replace/prepend with \n
            return re.sub(r'(?:^|(?<=[\.\;\:\n]))\s*(' + pattern + r')', r'\n\1', text)

        sec_content = safe_split(sec_content, r'\(\d+\)')
        sec_content = safe_split(sec_content, r'\([a-z]\)')
        sec_content = safe_split(sec_content, r'\([ivx]+\)')
        
        # Also handle "Provided that" and "Explanation" newlines - these usually start distinct blocks
        sec_content = re.sub(r'(Provided\s+that)', r'\n\n\1', sec_content)
        sec_content = re.sub(r'(Explanation\s*[\.—])', r'\n\n\1', sec_content)
        
        lines = sec_content.split('\n')
        formatted_lines = []
        is_definitions = "Definitions" in title
        
        for line in lines:
            line = line.strip().strip('_')  # Remove orphaned underscores
            if not line: continue
            
            # Sub-sections (1), (2)
            sub_m = re.match(r'^(\(\d+\))(.*)', line)
            if sub_m:
                formatted_lines.append(f"**{sub_m.group(1)}** {sub_m.group(2).strip()}\n")
                continue
                
            # Clauses (a), (b)
            cl_m = re.match(r'^(\([a-z]\))(.*)', line)
            if cl_m:
                c_id = cl_m.group(1)
                c_text = cl_m.group(2).strip()
                if is_definitions:
                    c_text = re.sub(r'["“]([^"”]+)["”]', r'_“\1”_', c_text, count=1)
                formatted_lines.append(f"- **{c_id}** {c_text}\n")
                continue
                
            # Sub-clauses (i), (ii)
            sc_m = re.match(r'^(\([ivx]+\))(.*)', line)
            if sc_m:
                formatted_lines.append(f"    - **{sc_m.group(1)}** {sc_m.group(2).strip()}\n")
                continue
                
            # Special markers
            if line.startswith("Explanation"):
                # Remove leading dash if present in the rest of the line
                content_after = re.sub(r'^Explanation\s*[\.—]\s*[—\-]*\s*', '', line)
                formatted_lines.append(f"**Explanation.—**\n{content_after}\n")
                continue
                
            formatted_lines.append(f"{line}\n")
            
        formatted.append("\n".join(formatted_lines))
        formatted.append("\n---\n\n")
        
        if next_extra:
            formatted.append(f"**{next_extra}**\n\n")
            
    # Post-process to remove double dashes
    res = "".join(formatted)
    res = re.sub(r'\*\*Explanation.—\*\*\n[—\-]+\s*', r'**Explanation.—**\n', res)
    return res, last_sec_num + 1

def process_bnss(input_path, output_dir):
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
    input_file = r'c:\Met4l.DSCode\Python\Embedding-Test-Py\documents\BNSS\bnss.md'
    output_folder = r'c:\Met4l.DSCode\Python\Embedding-Test-Py\documents\BNSS\output'
    process_bnss(input_file, output_folder)
