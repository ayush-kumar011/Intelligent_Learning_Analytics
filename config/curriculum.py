"""Reference curriculum: subject -> [(topic, difficulty 1-3)]."""
CURRICULUM = {
    "Mathematics": [("Algebra", 1), ("Limits", 2), ("Differentiation", 2), ("Integration", 3), ("Linear Algebra", 3), ("Probability", 2)],
    "Physics": [("Kinematics", 1), ("Newton's Laws", 1), ("Work & Energy", 2), ("Thermodynamics", 2), ("Electrostatics", 3), ("Waves & Optics", 2)],
    "Chemistry": [("Atomic Structure", 1), ("Chemical Bonding", 2), ("Stoichiometry", 2), ("Thermochemistry", 3), ("Organic Basics", 3), ("Acids & Bases", 2)],
    "Computer Science": [("Programming Basics", 1), ("Data Structures", 2), ("Algorithms", 3), ("Databases & SQL", 2), ("Operating Systems", 3), ("Computer Networks", 2)],
    "Statistics": [("Descriptive Statistics", 1), ("Probability Distributions", 2), ("Hypothesis Testing", 3), ("Regression", 3), ("Sampling", 2), ("Bayesian Basics", 3)],
    "English": [("Grammar", 1), ("Vocabulary", 1), ("Reading Comprehension", 2), ("Essay Writing", 2), ("Technical Writing", 2), ("Presentation Skills", 2)],
}
ACTIVITY_TYPES = ["Video Lecture", "Reading", "Practice Exercises", "Discussion", "Revision"]
MATERIAL_TYPES = ["Video Lecture", "Reading", "Practice Set"]
LEVELS = ["Beginner", "Intermediate", "Advanced"]
