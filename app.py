import streamlit as st
import pandas as pd
import ast

from typing import List

# --- Ρύθμιση σελίδας ---
st.set_page_config(page_title="Test Κατανομής Μαθητών", layout="wide")

# --- Κωδικός πρόσβασης ---
SECURITY_CODE = "katanomi2025"
with st.expander("🔐 Εισαγωγή Κωδικού Πρόσβασης"):
    code = st.text_input("Εισάγετε τον κωδικό:", type="password")
    if code != SECURITY_CODE:
        st.warning("Μη έγκυρος κωδικός.")
        st.stop()

st.title("🧪 Έλεγχος Λειτουργίας Κατανομής Μαθητών")

# --- Ανέβασμα αρχείου Excel ---
uploaded_file = st.file_uploader("📥 Ανέβασε το αρχείο Excel με τους μαθητές", type="xlsx")

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    def map_gender(g):
        return "F" if str(g).strip() == "Κ" else "M"

    def yes_no(value):
        return str(value).strip().lower() == "ναι"

    name_to_id = {name: idx + 1 for idx, name in enumerate(df["Όνομα"])}

    def parse_names_to_ids(cell):
        if pd.isna(cell):
            return []
        names = [n.strip() for n in str(cell).split(";") if n.strip()]
        return [name_to_id.get(n) for n in names if name_to_id.get(n)]

    students = []
    for idx, row in df.iterrows():
        student = {
            "id": idx + 1,
            "name": row["Όνομα"],
            "gender": map_gender(row["Φύλο"]),
            "is_teacher_child": yes_no(row["Παιδί Εκπαιδευτικού"]),
            "is_lively": yes_no(row["Ζωηρός"]),
            "is_special": yes_no(row["Ιδιαιτερότητα"]),
            "is_language_support": not yes_no(row["Καλή γνώση Ελληνικών"]),
            "friends": parse_names_to_ids(row.get("Φίλος/Φίλη")),
            "conflicts": parse_names_to_ids(row.get("Συγκρούσεις")),
        }
        students.append(student)

    num_classes = 2
    classes: List[List[dict]] = [[] for _ in range(num_classes)]

    def is_in_class(s_id, classes):
        return any(s_id in [s['id'] for s in cl] for cl in classes)

    def has_conflict(student, cl):
        return any(conflict_id in [s['id'] for s in cl] for conflict_id in student.get('conflicts', []))

    def assign_teacher_children(students, classes):
        teacher_children = [s for s in students if s['is_teacher_child']]
        num_classes = len(classes)
        distributed_ids = set()
        for i in range(min(num_classes, len(teacher_children))):
            child = teacher_children[i]
            classes[i].append(child)
            distributed_ids.add(child['id'])
        for child in [s for s in teacher_children if s['id'] not in distributed_ids]:
            classes[0].append(child)

    def assign_friends_of_teacher_children(students, classes):
        student_map = {s['id']: s for s in students}
        teacher_children_ids = [s['id'] for s in students if s['is_teacher_child']]
        for i, cl in enumerate(classes):
            teacher_kids_in_class = [s for s in cl if s['id'] in teacher_children_ids]
            if len(teacher_kids_in_class) >= 2:
                for tk in teacher_kids_in_class:
                    for fid in tk.get('friends', []):
                        friend = student_map.get(fid)
                        if (friend and tk['id'] in friend.get('friends', []) and
                            not friend['is_teacher_child'] and not friend['is_lively'] and
                            not has_conflict(friend, cl) and not is_in_class(friend['id'], classes)):
                            cl.append(friend)

    def assign_lively_students(students, classes):
        lively_students = [s for s in students if s['is_lively']]
        for student in lively_students:
            candidate_classes = []
            for i, cl in enumerate(classes):
                lively_count = sum(1 for s in cl if s['is_lively'])
                if lively_count >= 2: continue
                if any(s['id'] in student.get('friends', []) and student['id'] in s.get('friends', []) for s in cl):
                    continue
                if has_conflict(student, cl): continue
                candidate_classes.append((i, cl, lively_count, len(cl)))
            if not candidate_classes:
                for cl in classes:
                    if not has_conflict(student, cl):
                        cl.append(student)
                        break
            else:
                candidate_classes.sort(key=lambda x: (x[2], len([s for s in x[1] if s['gender'] == student['gender']]), x[3]))
                classes[candidate_classes[0][0]].append(student)

    def assign_special_needs_students(students, classes):
        special_students = [s for s in students if s['is_special'] and not is_in_class(s['id'], classes)]
        for student in special_students:
            class_lively_counts = [(i, sum(1 for s in cl if s['is_lively'])) for i, cl in enumerate(classes)]
            min_lively = min(c for _, c in class_lively_counts)
            candidate_classes = [i for i, c in class_lively_counts if c == min_lively]
            final_classes = []
            for i in candidate_classes:
                cl = classes[i]
                if not has_conflict(student, cl):
                    final_classes.append((i, cl))
            if final_classes:
                final_classes.sort(key=lambda x: (
                    sum(1 for s in x[1] if s['is_special']),
                    sum(1 for s in x[1] if s['gender'] == student['gender']),
                    len(x[1])
                ))
                final_classes[0][1].append(student)

    def assign_language_needs_students(students, classes, max_class_size=25):
        def get_class_index_of(student_id):
            for i, cl in enumerate(classes):
                if any(s['id'] == student_id for s in cl):
                    return i
            return None

        def is_fully_mutual_friend(s, friend_id):
            friend = next((x for x in students if x['id'] == friend_id), None)
            return friend and s['id'] in friend.get('friends', [])

        def count_gender(cl, gender):
            return sum(1 for s in cl if s['gender'] == gender)

        language_students = [s for s in students if s['is_language_support'] and not is_in_class(s['id'], classes)]
        for student in language_students:
            placed = False
            for friend_id in student.get('friends', []):
                if not is_fully_mutual_friend(student, friend_id): continue
                class_index = get_class_index_of(friend_id)
                if class_index is not None:
                    cl = classes[class_index]
                    if not has_conflict(student, cl) and len(cl) < max_class_size:
                        cl.append(student)
                        placed = True
                        break
            if placed: continue
            candidate_classes = []
            for i, cl in enumerate(classes):
                if has_conflict(student, cl) or len(cl) >= max_class_size:
                    continue
                lang_count = sum(1 for s in cl if s.get('is_language_support'))
                gender_count = count_gender(cl, student['gender'])
                candidate_classes.append((i, cl, lang_count, gender_count, len(cl)))
            if candidate_classes:
                candidate_classes.sort(key=lambda x: (x[2], x[3], x[4]))
                best_index = candidate_classes[0][0]
                classes[best_index].append(student)

    def assign_remaining_students_without_friends(students, classes, max_class_size=25):
        def gender_balance_score(cl, gender):
            return sum(1 for s in cl if s['gender'] == gender)
        remaining_students = [s for s in students if not is_in_class(s['id'], classes)]
        for student in remaining_students:
            candidate_classes = []
            for i, cl in enumerate(classes):
                if len(cl) >= max_class_size:
                    continue
                if has_conflict(student, cl):
                    continue
                gender_score = gender_balance_score(cl, student['gender'])
                candidate_classes.append((i, cl, gender_score, len(cl)))
            if candidate_classes:
                candidate_classes.sort(key=lambda x: (x[2], x[3]))
                best_class = candidate_classes[0][1]
                best_class.append(student)

    if st.button("▶️ Ξεκίνα την Κατανομή"):
        assign_teacher_children(students, classes)
        assign_friends_of_teacher_children(students, classes)
        assign_lively_students(students, classes)
        assign_special_needs_students(students, classes)
        assign_language_needs_students(students, classes)
        assign_remaining_students_without_friends(students, classes)

        for i, cl in enumerate(classes):
            st.markdown(f"### 🏫 Τμήμα {i+1} ({len(cl)} μαθητές)")
            st.dataframe(pd.DataFrame(cl))