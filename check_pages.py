import fitz

doc = fitz.open('documents/Bharatiya Nagarik Suraksha Sanhita (BNSS).pdf')
for i in range(20):
    text = doc[i].get_text()
    has_be = "BE it enacted" in text
    has_arr = "ARRANGEMENT" in text
    print(f"Page {i+1}: BE it enacted={has_be}, ARRANGEMENT={has_arr}")
