import re
import os

def normalize_text(text):
    # Remove page markers
    text = re.sub(r'## Page \d+\n?', '', text)
    text = re.sub(r'<page_number>.*?</page_number>\n?', '', text)
    text = re.sub(r'&lt;page_number&gt;.*?&lt;/page_number&gt;\n?', '', text)
    text = re.sub(r'---\n?', '', text)
    
    # Remove extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def parse_units(content):
    # Split by PART or CHAPTER
    # We use a lookahead to keep the delimiters
    pattern = re.compile(r'(?:\n|^)\s*(?:\*\*)?((?:PART|CHAPTER)\s+[IVXLCDM]+)(?:\*\*)?\s*[\r\n]+', re.MULTILINE)
    
    matches = list(pattern.finditer(content))
    units = []
    
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(content)
        
        header = match.group(1).strip()
        body = content[match.end():end].strip()
        
        # Extract title: the first line of the body that isn't empty or another header start
        lines = body.split('\n')
        title = ""
        for line in lines:
            line = line.strip().strip('* ')
            if line and not re.match(r'^(?:PART|CHAPTER|Section|\[SEC\])', line):
                title = line
                body = body[body.find(line)+len(line):].strip()
                break
        
        units.append({
            'type': 'PART' if 'PART' in header else 'CHAPTER',
            'id': header,
            'title': title,
            'content': body
        })
    
    return units

def format_section_blocks(content, expected_next_num):
    # Normalize section headers: **1. Title.**— -> [SEC] 1. 
    content = re.sub(r'(?:\n|^)\s*(?:\*\*)?(\d+)\.\s+', r'\n[SEC] \1. ', content)
    
    parts = re.split(r'\n\[SEC\] (\d+)\.\s+', content)
    formatted = []
    
    if parts[0].strip():
        formatted.append(parts[0].strip() + "\n\n")
        
    last_sec_num = expected_next_num - 1
    
    for i in range(1, len(parts), 2):
        orig_num = int(parts[i])
        sec_content = parts[i+1].strip()
        
        if orig_num < last_sec_num and orig_num <= 10:
            sec_num = last_sec_num + 1
        else:
            sec_num = orig_num
        last_sec_num = sec_num
        
        # Title extraction
        title = "Untitled"
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
        sec_content = safe_split(sec_content, r'\([a-z]\)')
        sec_content = safe_split(sec_content, r'\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)\)')
        
        # Keywords
        sec_content = re.sub(r'(Provided\s+further\s+that|Provided\s+also\s+that|Provided\s+that)', r'\n\n\1', sec_content)
        sec_content = safe_split(sec_content, r'Explanation\s*[\d\.]*[\.—]')
        sec_content = safe_split(sec_content, r'Illustration\s*s?[\d\.]*[\.—]?')
        
        # Bold specific Sanhitas
        sanhitas = ["Bharatiya Sakshya Adhiniyam, 2023", "Bharatiya Nagarik Suraksha Sanhita, 2023", "Bharatiya Nyaya Sanhita, 2023", "Information Technology Act, 2000"]
        for s in sanhitas:
            sec_content = re.sub(r'(?<!\*\*)' + re.escape(s), r'**' + s + r'**', sec_content)

        lines = sec_content.split('\n')
        formatted_lines = []
        is_definitions = "Definitions" in title
        in_illustrations = False
        indent_level = ""
        last_clause_letter = None
        
        for line in lines:
            line = line.strip().strip('_')
            if not line:
                if formatted_lines and formatted_lines[-1] != "\n":
                    formatted_lines.append("\n")
                continue
            
            # Sub-sections (1), (2)
            sub_m = re.match(r'^(\(\d+\))(.*)', line)
            if sub_m:
                formatted_lines.append(f"**{sub_m.group(1)}** {sub_m.group(2).strip()}\n")
                indent_level = ""
                in_illustrations = False
                last_clause_letter = None
                continue

            # Roman Numerals (i), (ii) - Sub-clauses OR Illustration items
            roman_m = re.match(r'^(\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii)\))(.*)', line)
            
            # Clauses (a), (b)
            cl_m = re.match(r'^(\([a-z]\))(.*)', line)
            
            if cl_m:
                c_id = cl_m.group(1)
                letter = c_id[1]
                
                # Sequence check to terminate illustrations
                is_next_clause = False
                if last_clause_letter:
                    if ord(letter) == ord(last_clause_letter) + 1:
                        is_next_clause = True
                    elif last_clause_letter == 'h' and letter == 'i':
                         is_next_clause = True
                
                # Context check for (i), (v), (x)
                is_roman = False
                if not is_next_clause:
                    if letter == 'i' and last_clause_letter != 'h' and not in_illustrations:
                        is_roman = True
                    elif letter == 'v' and last_clause_letter != 'u' and not in_illustrations:
                        is_roman = True
                    elif letter == 'x' and last_clause_letter != 'w' and not in_illustrations:
                        is_roman = True
                
                if (is_roman or in_illustrations) and not is_next_clause:
                    # Handle as Roman
                    r_id = c_id
                    r_text = cl_m.group(2).strip()
                    if in_illustrations:
                        formatted_lines.append(f"{indent_level}{r_id} {r_text}\n")
                    else:
                        formatted_lines.append(f"{indent_level}- **{r_id}** {r_text}\n")
                    continue
                else:
                    # Handle as Clause
                    in_illustrations = False
                    c_text = cl_m.group(2).strip()
                    if is_definitions:
                        c_text = re.sub(r'["“]([^"”]+)["”]', r'_“\1”_', c_text, count=1)
                    formatted_lines.append(f"- **{c_id}** {c_text}\n")
                    indent_level = "    "
                    last_clause_letter = letter
                    continue

            # Catch-all for roman
            if roman_m:
                r_id = roman_m.group(1)
                r_text = roman_m.group(2).strip()
                if in_illustrations:
                    formatted_lines.append(f"{indent_level}{r_id} {r_text}\n")
                else:
                    formatted_lines.append(f"{indent_level}- **{r_id}** {r_text}\n")
                continue

            # Illustrations/Explanations
            if line.startswith("Explanation") or line.startswith("Illustration"):
                 label_match = re.match(r'^(Explanation\s*\d*\s*[\.—]|Illustration\s*s?\s*\d*\s*[\.—]?)(.*)', line)
                 if label_match:
                     label_raw = label_match.group(1).strip().strip(".-—")
                     if "Illustration" in label_raw:
                         label = "Illustrations" if "s" in label_raw.lower() or "Illustration" == label_raw else "Illustration"
                         label = label + ".—"
                         in_illustrations = True
                     else:
                         num_m = re.search(r'\d+', label_raw)
                         label = f"Explanation {num_m.group(0)}.—" if num_m else "Explanation.—"
                         in_illustrations = False
                     
                     content_after = label_match.group(2).strip().strip("— -")
                     formatted_lines.append(f"{indent_level}**{label}**\n")
                     if content_after:
                         formatted_lines.append(f"{indent_level}{content_after}\n")
                     continue
            
            # Fallthrough
            formatted_lines.append(f"{indent_level}{line}\n")
            
        # Join lines and remove multiple consecutive newlines
        body = "".join(formatted_lines)
        body = re.sub(r'\n{3,}', '\n\n', body)
        formatted.append(body)
        formatted.append("\n---\n\n")
            
    res = "".join(formatted)
    return res, last_sec_num + 1

def process_bsa(input_path, output_dir):
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    content = normalize_text(content)
    
    units = parse_units(content)
    print(f"Total Parts/Chapters Found: {len(units)}")
    
    global_sec_num = 1
    current_part_header = ""
    
    for unit in units:
        if unit['type'] == 'PART':
            # Store part header and title for the next chapter
            p_id = unit['id']
            p_title = unit['title']
            current_part_header = f"# {p_id}\n\n"
            if p_title:
                current_part_header += f"# {p_title}\n\n"
            continue
            
        # Chapter unit
        c_id = unit['id']
        c_title = unit['title']
        
        # Clean title for filename
        clean_title = c_title.lower()
        clean_title = re.sub(r'[^a-z0-9]+', '_', clean_title).strip('_')
        roman_num = c_id.split(' ')[1].lower()
        filename = f"chapter_{roman_num}_{clean_title}.md"
        filepath = os.path.join(output_dir, filename)
        
        # Build content
        formatted_content = current_part_header
            
        formatted_content += f"# {c_id}\n\n## {c_title}\n\n---\n\n"
        
        sec_formatted, next_sec_num = format_section_blocks(unit['content'], global_sec_num)
        formatted_content += sec_formatted
        global_sec_num = next_sec_num
        
        # Final cleanup
        formatted_content = re.sub(r'\n{4,}', '\n\n', formatted_content)
        formatted_content = formatted_content.strip()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(formatted_content)
        print(f"Generated: {filename} (Sections up to {global_sec_num - 1})")

if __name__ == "__main__":
    input_file = r'c:\Met4l.DSCode\Python\Embedding-Test-Py\documents\bsa.md'
    output_folder = r'c:\Met4l.DSCode\Python\Embedding-Test-Py\documents\BSA'
    process_bsa(input_file, output_folder)
