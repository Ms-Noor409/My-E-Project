# My-E-Project
Full-featured  Noor Jewellry E-Commerce Website with user shopping experience and admin management dashboard.

NOOR Jewelry Store E-Commerce
A modern jewelry store web application built with Python and Flask.
This project includes product display, database integration, and a recommendation system using machine learning.

Features
User-friendly jewelry store UI
Product listing system
Database integration
Recommendation system using cosine similarity
Responsive frontend
Flask backend
Static assets management

Technologies Used
Python
Flask
HTML/CSS/JavaScript
SQLite
Machine Learning
Pickle Models

Project Structure
Bash
NOOR-JEWELRY-STORE-ECOM/
│
├── static/
│   ├── css/
│   ├── fonts/
│   ├── img/
│   └── js/
│
├── templates/
│
├── main.py
├── db_setup.py
├── db_utils.py
├── database.db
├── cosine_sim.pkl
├── dataset.pkl
└── vectorizer.pkl

Installation
1️⃣ Clone Repository
Bash
git clone https://github.com/your-username/NOOR-JEWELRY-STORE-ECOM.git
2️⃣ Open Project Folder
Bash
cd NOOR-JEWELRY-STORE-ECOM
3️⃣ Create Virtual Environment
Bash
python -m venv .venv
4️⃣ Activate Environment
Windows
Bash
.venv\Scripts\activate
Linux/Mac
Bash
source .venv/bin/activate
5️⃣ Install Requirements
Bash
pip install flask
(agar requirements.txt ho to:)
Bash
pip install -r requirements.txt
6️⃣ Run Project
Bash
python main.py

Machine Learning Files:
cosine_sim.pkl → similarity matrix
dataset.pkl → processed dataset
vectorizer.pkl → text vectorizer
