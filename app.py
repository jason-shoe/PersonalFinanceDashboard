from flask import Flask, render_template, request, g, redirect, url_for, jsonify
import sqlite3
import io
import csv
from datetime import datetime, date
import os
from flask import current_app, g

app = Flask(__name__, instance_relative_config=True)
app.config.from_mapping(
    SECRET_KEY='dev',
    DATABASE=os.path.join(app.instance_path, 'flaskr.sqlite'),
)

TRANSACTIONSDATABASE="transactions.db"

def get_db():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, TRANSACTIONSDATABASE)
    db = sqlite3.connect(db_path)
    return db

def insert_val(venmo_list, filename):
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, TRANSACTIONSDATABASE)
    db = sqlite3.connect(db_path)
    with sqlite3.connect(db_path) as curr:  
        conn = curr.cursor()
        values = (datetime.now().timestamp(),datetime.now().strftime("%d/%m/%y"), filename)
        s = conn.execute("""SELECT * FROM files WHERE filename == (?)""",[filename]).fetchall()
        if(len(s) != 0):
            return
        conn.execute("""INSERT OR REPLACE INTO files VALUES (?, ?, ?)""", values)
        for x in range(len(venmo_list)):
            ##venmo
            if(list(venmo_list[0])[0]=="Username"):
                s = venmo_list[x]['Datetime'].replace('T',' ')
                if(s != ''):
                    curr_date = datetime.strptime(s,'%Y-%m-%d %H:%M:%S')
                    amount = venmo_list[x]['Amount (total)'].replace('$','').replace(' ','').replace('+','')
                    values = (curr_date, curr_date.strftime("%d/%m/%y"), venmo_list[x]['Note'],venmo_list[x]['From'], venmo_list[x]['To'], amount,venmo_list[x]['Funding Source'],venmo_list[x]['Destination'],100.0)
                    conn.execute("""INSERT OR IGNORE INTO venmo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""", values)
                    conn.execute("""INSERT OR IGNORE INTO allData VALUES (?, ?, ?,?)""", [curr_date, venmo_list[x]['Note'], amount, "Venmo"])
            ##debitcard
            if(list(venmo_list[x])[0]=="Description" and x > 4):
                curr_date = datetime.strptime(list(venmo_list[x].values())[0],'%m/%d/%Y')
                values = (curr_date, curr_date.strftime("%d/%m/%y"), list(venmo_list[x].values())[1], list(venmo_list[x].values())[2], list(venmo_list[x].values())[3][0])
                conn.execute("""INSERT INTO debit VALUES (?, ?, ?, ?, ?)""", values)
                if("PMNT SENT Visa Direct NY".lower() not in list(venmo_list[x].values())[1].lower() and "BANK OF AMERICA CREDIT CARD Bill Payment".lower() != list(venmo_list[x].values())[1].lower()):
                    conn.execute("""INSERT OR IGNORE INTO allData VALUES (?, ?, ?, ?)""", [curr_date, list(venmo_list[x].values())[1], list(venmo_list[x].values())[2], "Debit"])
                else:
                    print(list(venmo_list[x].values())[1].lower())
            ##credit card
            if(list(venmo_list[0])[0]=="Posted Date"):
                curr_date = datetime.strptime(venmo_list[x]['Posted Date'],'%m/%d/%Y')
                values = (curr_date,curr_date.strftime("%d/%m/%y"), venmo_list[x]['Payee'],venmo_list[x]['Address'], venmo_list[x]['Amount'])
                conn.execute("""INSERT INTO credit VALUES (?, ?, ?, ?, ?)""", values)
                if("PAYMENT - THANK YOU".lower() != venmo_list[x]['Payee'].lower()):
                    conn.execute("""INSERT OR IGNORE INTO allData VALUES (?, ?, ?,?)""", [curr_date, venmo_list[x]['Payee'], venmo_list[x]['Amount'], "Credit"])
                else:
                    print(venmo_list[x]['Payee'].lower())

    curr.commit()
    conn.close()
@app.route('/get_all_data')
def get_all_data():
    conn = get_db().cursor()
    s = conn.execute("""SELECT 
                            *
                        FROM
                            alLData
                        ORDER BY 
                            datetime DESC""").fetchall()
    return jsonify(s)
@app.route('/get_all')
def get_all():
    conn = get_db().cursor()
    s = conn.execute("""SELECT 
                            c.datetime, (SELECT SUM(amount) FROM allData d WHERE d.datetime <= c.datetime), c.description 
                        FROM 
                            allData c 
                        WHERE
                            datetime > DATE('now','-1 year')
                        GROUP BY
                            c.datetime
                        ORDER BY 
                            c.datetime DESC""").fetchall()
    return jsonify(s)
@app.route('/get_debit_data')
def get_debit_data():
    conn = get_db().cursor()
    s = conn.execute("""SELECT 
                            datestring, balance FROM debit 
                        WHERE 
                            datetime > DATE('now','-1 year') 
                        ORDER BY datetime DESC """).fetchall()
    return jsonify(s)
@app.route('/get_credit_data')
def get_credit_data():
    conn = get_db().cursor()
    s = conn.execute("""SELECT 
                            c.datestring, (SELECT -1*SUM(amount) FROM credit d WHERE d.datetime <= c.datetime), c.payee 
                        FROM 
                            credit c 
                        WHERE
                            datetime > DATE('now','-1 year')
                        GROUP BY 
                            datestring 
                        ORDER BY 
                            c.datetime DESC""").fetchall()
    return jsonify(s)
@app.route('/get_venmo_data')
def get_venmo_data():
    conn = get_db().cursor()
    s = conn.execute("""SELECT 
                            c.datestring, 
                            (SELECT 
                                SUM(amount) 
                                    FROM 
                                        venmo d 
                                    WHERE 
                                        d.datetime <= c.datetime AND (funding_src == "Venmo balance" OR destination == "Venmo balance")) 
                        FROM 
                            venmo c
                        WHERE
                            datetime > DATE('now','-1 year')
                        ORDER BY 
                            c.datetime DESC""").fetchall()
    return jsonify(s)

@app.route('/get_dates')
def get_dates():
    conn = get_db().cursor()
    s = conn.execute("""SELECT 
                            100*strftime('%Y', date)+strftime('%W', date) AS WeekNum 
                        FROM 
                        (WITH RECURSIVE dates(date) AS (
                        VALUES((SELECT min(datetime) FROM debit))
                        UNION ALL
                        SELECT 
                            date(date, '+1 day')
                        FROM 
                            dates
                        WHERE 
                            date < (SELECT max(datetime) FROM debit) AND date > DATE('now','-1 year')
                        )
                        SELECT date FROM dates)
                        GROUP BY 
                            WeekNum;""").fetchall()
    return jsonify(s)
@app.route('/get_debit_data_weekly')
def get_debit_data_weekly():
    conn = get_db().cursor()
    s = conn.execute("""SELECT 
                            datetime, WeekNumber, SUM(amount), start, end 
                        FROM 
                            (SELECT 
                                datetime, amount, 100*strftime('%Y', datetime)+strftime('%W', datetime) WeekNumber, strftime('%m/%d', DATE(datetime, 'Weekday 0','-6 days')) start, strftime('%m/%d',DATE(datetime, 'Weekday 0')) end 
                            FROM 
                                allData 
                            WHERE 
                                amount > 0 AND datetime > DATE('now','-1 year')) 
                        GROUP BY 
                            WeekNumber""").fetchall()
    res = list(map(list, s)) 
    for x in range(len(res)):
        t = conn.execute("""SELECT description, SUM(amount) 
                            FROM 
                                (SELECT description, datetime, amount, 100*strftime('%Y', datetime)+strftime('%W', datetime) WeekNumber 
                                FROM 
                                    allData 
                                WHERE 
                                    amount > 0 AND datetime > DATE('now','-1 year') AND WeekNumber = (?) ) 
                            GROUP BY 
                                description, WeekNumber""", [res[x][1]]).fetchall()
        u = list(map(list,t))
        res[x].append([])
        res[x].append([])
        for y in range(len(u)):
            res[x][5].append(u[y][0])
            res[x][6].append(str(u[y][1]))
    return jsonify(res)
@app.route('/get_credit_data_weekly')
def get_credit_data_weekly():
    conn = get_db().cursor()
    s = conn.execute("""SELECT 
                            datetime, WeekNumber, -1*SUM(amount), start, end 
                        FROM 
                            (SELECT 
                                datetime, amount, 100*strftime('%Y', datetime)+strftime('%W', datetime) WeekNumber, strftime('%m/%d', DATE(datetime, 'Weekday 1','-7 days')) start, strftime('%m/%d',DATE(datetime, 'Weekday 0')) end 
                            FROM 
                                allData 
                            WHERE 
                                amount <0 AND datetime > DATE('now','-1 year')) 
                        GROUP BY 
                            WeekNumber""").fetchall()
    res = list(map(list, s)) 
    for x in range(len(res)):
        t = conn.execute("""SELECT 
                                description, -1*SUM(amount) 
                            FROM 
                                (SELECT 
                                    description, datetime, amount, 100*strftime('%Y', datetime)+strftime('%W', datetime) WeekNumber 
                                FROM 
                                    allData 
                                WHERE 
                                    amount < 0 AND WeekNumber = (?) ) 
                            GROUP BY 
                                description, WeekNumber""", [res[x][1]]).fetchall()
        u = list(map(list,t))
        res[x].append([])
        res[x].append([])
        for y in range(len(u)):
            res[x][5].append(u[y][0])
            res[x][6].append(str(u[y][1]))
    return jsonify(res)

@app.route("/get_income_data")
def get_income_data():
    incomeName = request.args.get("incomeName", type=str)
    print(incomeName)
    conn = get_db().cursor()
    s = conn.execute("""SELECT 
                            datetime, WeekNumber, SUM(amount), start, end 
                        FROM 
                            (SELECT 
                                datetime, amount, 100*strftime('%Y', datetime)+strftime('%W', datetime) WeekNumber,strftime('%m/%d', DATE(datetime, 'Weekday 1','-7 days')) start, strftime('%m/%d',DATE(datetime, 'Weekday 0')) end 
                            FROM 
                                debit 
                            WHERE 
                                description==(?) AND amount >0 AND datetime > DATE('now','-1 year')) 
                        GROUP BY 
                            WeekNumber""",[incomeName]).fetchall()
    res = list(map(list, s)) 
    for x in range(len(res)):
        t = conn.execute("""SELECT description, SUM(amount) 
                            FROM 
                                (SELECT description, datetime, amount, 100*strftime('%Y', datetime)+strftime('%W', datetime) WeekNumber 
                                FROM 
                                    debit 
                                WHERE 
                                    description==(?) AND amount >0 AND datetime > DATE('now','-1 year') AND WeekNumber = (?) ) 
                            GROUP BY WeekNumber""", [incomeName, res[x][1]]).fetchall()
        u = list(map(list,t))
        res[x].append([])
        res[x].append([])
        for y in range(len(u)):
            res[x][5].append(u[y][0])
            res[x][6].append(str(u[y][1]))
    return jsonify(res)

@app.route('/')
def upload_file():
    conn = get_db().cursor()
    s = conn.execute("""SELECT * FROM venmo ORDER BY datetime DESC""").fetchall()
    t = conn.execute("""SELECT * FROM files ORDER BY date DESC""").fetchall()
    u = conn.execute("""SELECT * FROM credit ORDER BY datetime DESC""").fetchall()
    v = conn.execute("""SELECT * FROM debit ORDER BY datetime DESC""").fetchall()


    return render_template('upload.html', venmo = s, files=t, credit=u, debit=v)

@app.route('/graph')
def display_graph():
    conn = get_db().cursor()
    s = conn.execute("""SELECT description 
                        FROM 
                            (SELECT 
                                d.description, (SELECT
                                                    COUNT(c.amount)
                                                FROM
                                                    debit c
                                                WHERE
                                                    d.description == c.description) AS total
                            FROM
                                debit d
                            WHERE
                                amount > 0 AND datetime > DATE('now','-1 year') AND total > 1
                            GROUP BY 
                                description
                            ORDER BY
                                total DESC)""").fetchall()
    t = round(conn.execute("""SELECT balance, MAX(datetime) from debit""").fetchall()[0][0]*10)/10
    u = round(conn.execute("""SELECT (SELECT -1*SUM(amount) FROM credit d WHERE d.datetime <= c.datetime), MAX(datetime), c.datetime from credit c""").fetchall()[0][0]*10)/10
    v = round(conn.execute("""SELECT (SELECT SUM(amount) FROM venmo d WHERE d.datetime <= c.datetime AND (funding_src == "Venmo balance" OR destination == "Venmo balance")) , MAX(datetime), c.datetime from venmo c""").fetchall()[0][0]*10)/10
    print(v)
    print(t)
    print("DATA")
    return render_template('graph.html',len=len(s), income=s, debitBalance=t, creditBalance=u,venmoBalance=v)

@app.route('/uploader', methods = ['GET', 'POST'])
def upload_files():
    if request.method == 'POST':
        f = request.files['file']
        if(len(f.filename) >= 3 and f.filename[-3:]=="csv"):
            fstring = f.read().decode("UTF8")
            csv_dicts = [{k: v for k, v in row.items()} for row in csv.DictReader(fstring.splitlines(), skipinitialspace=True)]
            insert_val(csv_dicts, f.filename)

            return redirect(url_for('upload_file'))
            
        else:
            return "not a csv"

@app.route('/initialize')
def initialize_db():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(BASE_DIR, TRANSACTIONSDATABASE)
    db = sqlite3.connect(db_path)
    with sqlite3.connect(db_path) as curr:  
        conn = curr.cursor()
        conn.execute("""DROP TABLE IF EXISTS files""")
        conn.execute("""CREATE TABLE files
                        (
                        date DATE UNIQUE,
                        datestring DATE,
                        filename VARCHAR(100) UNIQUE
                        )""")
        conn.execute("""DROP TABLE IF EXISTS venmo""")
        conn.execute("""CREATE TABLE venmo
                        (
                        datetime DATE UNIQUE,
                        datestring DATE,
                        note VARCHAR(100),
                        sender VARCHAR(100),
                        recipient VARCHAR(100),
                        amount FLOAT,
                        funding_src VARCHAR(100),
                        destination VARCHAR(100),
                        balance FLOAT
                        )""")
        conn.execute("""DROP TABLE IF EXISTS credit""")
        conn.execute("""CREATE TABLE credit
                        (
                        datetime DATE,
                        datestring DATE,
                        payee VARCHAR(100),
                        address VARCHAR(100),
                        amount FLOAT
                        )""")
        conn.execute("""DROP TABLE IF EXISTS debit""")
        conn.execute("""CREATE TABLE debit
                        (
                        datetime DATE,
                        datestring VARCHAR(100),
                        description VARCHAR(100),
                        amount FLOAT,
                        balance FLOAT
                        )""")
        conn.execute("""DROP TABLE IF EXISTS allData""")
        conn.execute("""CREATE TABLE allData
                        (
                        datetime DATE,
                        description VARCHAR(100),
                        amount FLOAT,
                        source VARCHAR(100)
                        )""")
    curr.commit()
    conn.close()
    return render_template('upload.html') 

if __name__ == '__main__':
   app.run(debug = True)