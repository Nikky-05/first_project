from flask import Flask, render_template, jsonify
import mysql.connector
from datetime import datetime, timedelta
import random
import schedule
import time
import threading
import smtplib
from email.mime.text import MIMEText
import ssl
from pytz import timezone

app = Flask(__name__)

# Database configuration
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': 'NKpallotti@99',
    'database': 'transaction_monitor'
}

# Email configuration
EMAIL_SENDER = 'nkbisane@gmail.com'
EMAIL_RECEIVER = 'ajabgajab1999@gmail.com'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USERNAME = 'ajabgajab1999@gmail.com'
SMTP_PASSWORD = 'NKbisen@99'  # Use an app-specific password if using Gmail

# To track the last sent email for each threshold
last_sent_thresholds = {4: False, 4.5: False, 5: False, 5.5: False, 6: False}

def get_db_connection():
    return mysql.connector.connect(**db_config)

def simulate_transactions():
    conn = get_db_connection()
    cursor = conn.cursor()
    transaction_types = ['collection', 'payout']
    for _ in range(10):  # Simulate 10 transactions per second
        txn_type = random.choice(transaction_types)
        status = 'success' if random.random() > 0.05 else 'failure'
        error_msg = '' if status == 'success' else 'Simulated failure'
        india = timezone('Asia/Kolkata')
        timestamp = datetime.now(india)

        cursor.execute(
            "INSERT INTO transactions (timestamp, transaction_type, status, error_message) VALUES (%s, %s, %s, %s)",
            (timestamp, txn_type, status, error_msg)
        )
    conn.commit()
    cursor.close()
    conn.close()

def check_error_rate():
    global last_sent_thresholds
    conn = get_db_connection()
    cursor = conn.cursor()
    one_min_ago = datetime.utcnow() - timedelta(minutes=1)
    cursor.execute(
        "SELECT COUNT(*) FROM transactions WHERE timestamp >= %s",
        (one_min_ago,)
    )
    total = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM transactions WHERE timestamp >= %s AND status = 'failure'",
        (one_min_ago,)
    )
    failures = cursor.fetchone()[0]
    if total > 0:
        error_rate = (failures / total) * 100
        print(f"Current error rate: {error_rate}%")

        # Check and send email if failure rate crosses any of the thresholds
        for threshold in [4, 4.5, 5, 5.5, 6]:
            if error_rate >= threshold and not last_sent_thresholds[threshold]:
                send_email_alert(error_rate, threshold)
                last_sent_thresholds[threshold] = True  # Mark this threshold as crossed

        # Reset thresholds if the error rate goes below 4% (or any other threshold you're tracking)
        if error_rate < 4:
            for threshold in last_sent_thresholds:
                last_sent_thresholds[threshold] = False

    cursor.close()
    conn.close()

def send_email_alert(error_rate, threshold):
    subject = f'Transaction Failure Alert: {threshold}% Threshold Crossed'
    body = f"""
    Dear User,

    The failure rate has reached {error_rate:.2f}%, which has crossed the {threshold}% threshold.

    Please check the system immediately for potential issues.

    Best regards,
    Transaction Monitoring System
    """
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER

    context = ssl.create_default_context()
    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls(context=context)
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())

def run_scheduler():
    schedule.every(1).seconds.do(simulate_transactions)  # Simulate transactions every second
    schedule.every(1).minutes.do(check_error_rate)  # Check error rate every minute
    while True:
        schedule.run_pending()
        time.sleep(1)

@app.route('/')
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query to get total transactions, successful transactions, and failed transactions by hour
    cursor.execute("""
    SELECT 
        HOUR(timestamp) AS hour,
        COUNT(*) AS total_transactions,
        SUM(CASE WHEN status = 'failure' THEN 1 ELSE 0 END) AS failed_transactions,
        COUNT(*) - SUM(CASE WHEN status = 'failure' THEN 1 ELSE 0 END) AS successful_transactions
    FROM transactions
    WHERE timestamp >= NOW() - INTERVAL 1 DAY
    GROUP BY hour
    ORDER BY hour
    """)

    # Fetch the result of the query
    data = cursor.fetchall()

    # Process the data to be sent to the template
    hours = [row[0] for row in data]  # Hours from 0 to 23
    total_transactions = [row[1] for row in data]
    failed_transactions = [row[2] for row in data]
    successful_transactions = [row[3] for row in data]

    cursor.close()
    conn.close()

    # Render the template and pass the data
    return render_template('dashboard.html', hours=hours,
                           total_transactions=total_transactions,
                           failed_transactions=failed_transactions,
                           successful_transactions=successful_transactions)


@app.route('/get_transaction_data')
def get_transaction_data():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT 
    h.hour,
    COALESCE(COUNT(t.id), 0) AS total_transactions,
    COALESCE(SUM(CASE WHEN t.status = 'failure' THEN 1 ELSE 0 END), 0) AS failed_transactions,
    COALESCE(SUM(CASE WHEN t.status = 'success' THEN 1 ELSE 0 END), 0) AS successful_transactions
FROM (
    SELECT 0 AS hour UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION
    SELECT 6 UNION SELECT 7 UNION SELECT 8 UNION SELECT 9 UNION SELECT 10 UNION SELECT 11 UNION
    SELECT 12 UNION SELECT 13 UNION SELECT 14 UNION SELECT 15 UNION SELECT 16 UNION SELECT 17 UNION
    SELECT 18 UNION SELECT 19 UNION SELECT 20 UNION SELECT 21 UNION SELECT 22 UNION SELECT 23
) AS h
LEFT JOIN transactions t ON HOUR(t.timestamp) = h.hour AND t.timestamp >= NOW() - INTERVAL 1 DAY
GROUP BY h.hour
ORDER BY h.hour
""")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return jsonify(data)


if __name__ == '__main__':
    threading.Thread(target=run_scheduler).start()
    app.run(host='0.0.0.0', port=5000 , debug=True)
