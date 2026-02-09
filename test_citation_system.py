import json
import urllib.request
import urllib.error

def test_citation_system():
    """Test the new law chip citation system."""
    
    test_queries = [
        "What is the punishment for theft?",
        "What are my rights during an arrest?",
        "How do I file an FIR?"
    ]
    
    all_sources = {}  # Simulate source registry
    
    print("=" * 80)
    print("TESTING UNIQUE SOURCE IDs & LAW CHIP CITATIONS")
    print("=" * 80)
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n{'='*80}")
        print(f"TEST {i}: {query}")
        print('='*80)
        
        try:
            # Make request
            data = json.dumps({'query': query, 'stream': False}).encode('utf-8')
            req = urllib.request.Request(
                'http://localhost:8000/api/v1/query',
                data,
                {'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=60) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                # Extract sources
                sources = result.get('sources', [])
                answer = result.get('answer', '')
                
                print(f"\n✓ Received {len(sources)} sources")
                
                # Test 1: UID Format
                print("\n[TEST 1] UID Format Check:")
                for src in sources:
                    uid = src.get('uid', 'MISSING')
                    chip = src.get('chip_label', 'MISSING')
                    law = src.get('law', 'MISSING')
                    section = src.get('section', 'MISSING')
                    
                    print(f"  - UID: {uid:20s} | Chip: {chip:15s} | Law: {law:6s} | Section: {section}")
                    
                    # Validate UID format
                    if uid == 'MISSING' or chip == 'MISSING':
                        print(f"    ❌ FAIL: Missing uid or chip_label")
                    else:
                        print(f"    ✓ PASS")
                
                # Test 2: Citation Chips in Answer
                print("\n[TEST 2] Citation Chips in Answer:")
                import re
                chips_in_answer = re.findall(r'\[([A-Z]+)(?::(\d+))?\]', answer)
                print(f"  Found {len(chips_in_answer)} citation chips in answer:")
                for law, section in chips_in_answer[:10]:  # Show first 10
                    chip_text = f"[{law}:{section}]" if section else f"[{law}]"
                    print(f"    - {chip_text}")
                
                # Test 3: Source Registry (Persistence)
                print("\n[TEST 3] Source Registry Update:")
                new_sources = 0
                duplicate_sources = 0
                
                for src in sources:
                    uid = src.get('uid')
                    if uid not in all_sources:
                        all_sources[uid] = src
                        new_sources += 1
                    else:
                        duplicate_sources += 1
                
                print(f"  - New sources added: {new_sources}")
                print(f"  - Duplicate sources (already in registry): {duplicate_sources}")
                print(f"  - Total unique sources in registry: {len(all_sources)}")
                
                # Test 4: Chip Label Consistency
                print("\n[TEST 4] Chip Label Consistency:")
                consistent = True
                for src in sources:
                    uid = src.get('uid', '')
                    chip = src.get('chip_label', '')
                    law = src.get('law', '')
                    section = src.get('section', '')
                    
                    # Reconstruct expected chip
                    if section and section != 'None':
                        section_main = section.split('(')[0].strip()
                        expected_chip = f"[{law.upper()}:{section_main}]"
                    else:
                        expected_chip = f"[{law.upper()}]"
                    
                    if chip != expected_chip:
                        print(f"  ❌ MISMATCH: {chip} != {expected_chip}")
                        consistent = False
                
                if consistent:
                    print("  ✓ All chip labels are consistent with law/section")
                
        except urllib.error.URLError as e:
            print(f"\n❌ ERROR: Could not connect to server")
            print(f"   {e}")
            return
        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    # Final Summary
    print(f"\n{'='*80}")
    print("FINAL SUMMARY")
    print('='*80)
    print(f"Total unique sources across all queries: {len(all_sources)}")
    print("\nSample UIDs in registry:")
    for uid in list(all_sources.keys())[:10]:
        src = all_sources[uid]
        print(f"  - {uid:20s} → {src['chip_label']}")
    
    print("\n✅ Testing complete!")

if __name__ == "__main__":
    test_citation_system()
