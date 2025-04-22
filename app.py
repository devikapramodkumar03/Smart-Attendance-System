from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file,make_response
import pandas as pd
import sqlite3
from datetime import datetime
import base64
import numpy as np
from io import BytesIO
import qrcode
import io


app = Flask(__name__)
app.secret_key = 'your_secret_key'

def init_db():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()
    
    # Create students table with encoding column
    c.execute('''CREATE TABLE IF NOT EXISTS students (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    student_id TEXT NOT NULL UNIQUE,
                    encoding TEXT
                )''')
    
    # Create attendance table
    c.execute('''CREATE TABLE IF NOT EXISTS attendance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    student_id TEXT,
                    name TEXT,
                    status TEXT,
                    date TEXT,
                    time TEXT,
                    method TEXT
                )''')
    
    conn.commit()
    conn.close()

# Initialize database
init_db()


# --- Admin Credentials ---
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'sharda123'

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']
        if user == ADMIN_USERNAME and pw == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if not session.get('admin'):
        return redirect(url_for('login'))
    return render_template('dashboard.html')

@app.route('/attendance')
def attendance():
    return render_template('attendance.html')

@app.route('/selection')
def loginselection():
    return render_template('loginselect.html')

@app.route('/manual_attendance', methods=['GET', 'POST'])
def manual_attendance():
    conn = sqlite3.connect('attendance.db')
    c = conn.cursor()

    if request.method == 'POST':
        if 'add_student' in request.form:
            name = request.form['name']
            student_id = request.form['student_id']
            c.execute("INSERT OR IGNORE INTO students (name, student_id) VALUES (?, ?)",
                      (name, student_id))
            conn.commit()
            flash(f"Student {name} added successfully.")

        elif 'mark_attendance' in request.form:
            now = datetime.now()
            date = now.strftime("%Y-%m-%d")
            time = now.strftime("%H:%M:%S")
            present_ids = request.form.getlist('present[]')

            c.execute("SELECT name, student_id FROM students")
            all_students = c.fetchall()

            # Process each student
            for name, student_id in all_students:
                status = 'Present' if student_id in present_ids else 'Absent'  # Correct status

                # Check if already marked
                c.execute('''SELECT * FROM attendance
                              WHERE student_id=? AND date=? AND method='manual' ''',
                            (student_id, date))
                already_marked = c.fetchone()

                # Insert/Update record
                if not already_marked:
                    c.execute('''INSERT INTO attendance
                               (student_id, name, status, date, time, method)
                               VALUES (?, ?, ?, ?, ?, ?)''',
                            (student_id, name, status, date, time, 'manual'))
                else:
                    c.execute('''UPDATE attendance SET status=?, time=?
                              WHERE student_id=? AND date=? AND method='manual' ''',
                            (status, time, student_id, date))

            conn.commit()  # Commit after processing all students
            flash("Attendance submitted successfully!")

    # Fetch student list (for both GET and POST requests)
    c.execute("SELECT name, student_id FROM students")
    students = c.fetchall()
    conn.close()

    return render_template('manual.html', students=students)


@app.route('/delete_student', methods=['POST'])
def delete_student():
    try:
        student_id = request.form['student_id']
        conn = sqlite3.connect('attendance.db')
        c = conn.cursor()
        
        # Check if there's only one student left
        c.execute("SELECT COUNT(*) FROM students")
        count = c.fetchone()[0]
        
        if count == 1:
            flash("Cannot delete the last student. Please add another student first.", 'error')
            return redirect(url_for('manual_attendance'))
        
        # Delete attendance records for the student
        c.execute("DELETE FROM attendance WHERE student_id = ?", (student_id,))
        
        # Delete the student from the students table
        c.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        
        conn.commit()
        conn.close()
        flash(f"Student with ID {student_id} has been deleted.", 'success')
    except Exception as e:
        flash(f"An error occurred: {e}", 'error')
    
    return redirect(url_for('manual_attendance'))

@app.route("/view_records")
def view_records():
    conn = sqlite3.connect("attendance.db")
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, name, status, date, method FROM attendance ORDER BY date DESC")

    records = cursor.fetchall()
    conn.close()
    return render_template("view_records.html", records=records)

@app.route("/export_excel")
def export_excel():
    conn = sqlite3.connect("attendance.db")
    df = pd.read_sql_query("SELECT student_id, name, status, date, method FROM attendance", conn)

    conn.close()

    output = BytesIO()
    df.to_excel(output, index=False, sheet_name="Attendance")
    output.seek(0)

    return send_file(output, as_attachment=True, download_name="attendance_records.xlsx", mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


@app.route('/register_face', methods=['GET', 'POST'])
def register_face():
    return render_template('face_registration.html')


@app.route('/mark_attendance', methods=['GET', 'POST'])
def mark_attendance():
    return render_template('face_attendance.html')

# --- DB Setup ---
def init_db():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    created_at DATETIME
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS attendees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER,
                    name TEXT,
                    is_present BOOLEAN DEFAULT 0,
                    timestamp DATETIME,
                    FOREIGN KEY (event_id) REFERENCES events(id)
                )''')
    conn.commit()
    conn.close()

init_db()

# --- Routes ---
@app.route('/edashboard')
def edashboard():
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('SELECT * FROM events')
    events = c.fetchall()
    conn.close()
    return render_template('edashboard.html', events=events)

@app.route('/create_event', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        event_name = request.form['event_name']
        attendee_names = request.form['attendee_names'].splitlines()

        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute('INSERT INTO events (name, created_at) VALUES (?, ?)', (event_name, datetime.now()))
        event_id = c.lastrowid

        for name in attendee_names:
            if name.strip():
                c.execute('INSERT INTO attendees (event_id, name) VALUES (?, ?)', (event_id, name.strip()))

        conn.commit()
        conn.close()

        return redirect(url_for('show_qr', event_id=event_id))
    return render_template('create_event.html')

@app.route('/qr/<int:event_id>')
def show_qr(event_id):
    url = request.url_root + 'mark_eattendance/' + str(event_id)
    return render_template('show_qr.html', event_id=event_id, qr_url=url_for('download_qr', event_id=event_id))

@app.route('/download_qr/<int:event_id>')
def download_qr(event_id):
    url = request.url_root + 'mark_eattendance/' + str(event_id)
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    response = make_response(send_file(buf, mimetype='image/png', as_attachment=True, download_name=f'event_{event_id}_qr.png'))
    return response

@app.route('/mark_eattendance/<int:event_id>', methods=['GET', 'POST'])
def mark_eattendance(event_id):
    message = ""
    if request.method == 'POST':
        name = request.form['name']
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute('SELECT * FROM attendees WHERE event_id = ? AND name = ?', (event_id, name))
        attendee = c.fetchone()
        if attendee:
            c.execute('UPDATE attendees SET is_present = 1, timestamp = ? WHERE id = ?', (datetime.now(), attendee[0]))
            conn.commit()
            message = f"Attendance marked for {name}!"
        else:
            message = "Name not found. Please enter a valid name."
        conn.close()
    return render_template('mark_eattendance.html', event_id=event_id, message=message)

@app.route('/view_attendance/<int:event_id>')
def view_attendance(event_id):
    conn = sqlite3.connect('data.db')
    c = conn.cursor()
    c.execute('SELECT name, is_present, timestamp FROM attendees WHERE event_id = ?', (event_id,))
    attendees = c.fetchall()
    conn.close()
    return render_template('view_attendance.html', attendees=attendees)

if __name__ == '__main__':
    app.run(debug=True)