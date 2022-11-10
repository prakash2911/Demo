import uuid
from flask import Flask, request, session
from flask_mysqldb import MySQL
import MySQLdb.cursors
import hashlib
from datetime import timedelta
from datetime import datetime
from flask_socketio import SocketIO,join_room,emit
from flask_cors import CORS 


app = Flask(__name__)
CORS(app)
app.secret_key = 'Tahve bqltuyej tbrjereq qobfd MvIaTq cmanmvpcuxsz iesh tihkel CnTu dretpyauritompeanstd '

app.config['MYSQL_HOST'] = 'brooklyn-db.mysql.database.azure.com'
app.config['MYSQL_USER'] = 'brooklyn'
app.config['MYSQL_PASSWORD'] = 'root@123'
app.config['MYSQL_DB'] = 'brooklyn'
app.config['MYSQL_PORT'] = 3306

socketio = SocketIO(app,cors_allowed_origins="*", ping_timeout=5, ping_interval=5)
mysql = MySQL(app)

@app.route('/login', methods=['POST'])
def login():
        email = request.json.get('email')
        password = request.json.get('password')
        hash_object = hashlib.sha256(password.encode('ascii'))
        hash_password = hash_object.hexdigest()
        returner = {}
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM accounts WHERE email = %s AND password = %s', (email, hash_password,))
        a = cursor.fetchone()
        if a:
            cursor.execute("select * from user where email = %s ",[a['email'],])
            account= cursor.fetchone()
            returner['status']="login success"
            returner['email'] = account['email']
            returner['username'] = account['username']
            returner['utype']=account['utype']
            returner['subtype'] = account['subtype']
            
            if account['utype']=='customer':
                cursor.execute('SELECT roomid FROM rooms where status = %s',['vacant'])
                roomid = cursor.fetchone()
                returner['roomid'] = roomid
                cursor.execute(f"UPDATE rooms SET status = 'occupied' where roomid =%s",[roomid,])
                mysql.connection.commit()
            else:
                cursor.execute('UPDATE service set status = "online"')
                mysql.connection.commit()
        else:
            returner['status']="login failure"
            returner['utype']="None"
        return returner

@app.route('/logout', methods=['POST'])
def logout():
   returner = {}
   cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
   if request.json.get("utype")=='customer':
    cursor.execute("UPDATE rooms SET status = 'vacant' where roomid =%s",[request.json.get("roomid"),])
    mysql.connection.commit()
   else:
    cursor.execute("UPDATE service SET status = 'offline' , room = null where email =%s",[request.json.get("email"),])
    mysql.connection.commit()
   returner['status']="logout success"
   return returner
   
@app.route('/register', methods=['POST'])
def register():
    returner = {}
    password = request.json.get('password')
    email = request.json.get('email')
    fname = request.json.get('fName')
    lname = request.json.get('lName')
    phone = request.json.get('phone')
    username = fname+" "+lname
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM accounts WHERE email = %s', (email,))
    account = cursor.fetchone()
    if account:
        returner['status']= 'Account already exists'
    else:
        hash_object = hashlib.sha256(password.encode('ascii'))
        hash_password = hash_object.hexdigest()   
        cursor.execute('INSERT INTO accounts VALUES (%s, %s)', (email, hash_password,))
        cursor.execute('INSERT INTO user VALUES (NULL, %s, %s, %s, %s, %s,%s, "None")', (username,fname,lname, phone, email,"customer",))
        mysql.connection.commit()
        returner['status']=  'You have successfully registered!'
        returner['utype'] = "customer"
    return returner

@app.route('/getDetails',methods = ['POST'])
def GetDetailsWithEmail():
    email = request.json.get('email')
    # print(email)
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT * FROM user WHERE email = %s', [email,])
    det = cursor.fetchone()
    print(det)
    return det

@app.route('/getPerformance',methods=['POST'])
def getpef():
    email = request.json.get('email')
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute('SELECT perfo FROM service WHERE email = %s', [email,])
    det = cursor.fetchone()
    return det

@socketio.on('getrequest',namespace='/chat')
def getreq(data):
    socketid = request.sid
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(f"update service set sid = '{socketid}' where email = %s",[data["email"],])
    mysql.connection.commit()

@socketio.on('join',namespace='/chat')
def join(data):
    join_room(data)
        
@socketio.on('accept',namespace='/chat')
def accept(message):
    cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cursor.execute(f"update service set room=%s where status = 'online' and email = %s " , [message['roomid'],message['email'],])
    mysql.connection.commit()
    cursor.execute(f"select subtype,perfo from service where email= %s",[message['email'],])
    det = cursor.fetchone()
    cursor.execute(f"select username from user where email = %s",[message['email'],])
    username = cursor.fetchone()
    print(det)
    emit("getdetails",{"name":username['username'],"subtype":det['subtype'],"performance":det['perfo']},to=message['roomid'],namespace="/chat")

@socketio.on('text' ,namespace='/chat')
def text(message):
    print(message)
    room = message['roomid']
    fm = message['fm']
    utype = message['utype']
    m = message['msg']
    email = message['email']
    if fm :
        context = 'finance'
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute(f"select sid from service where status = 'online' and room is null and subtype = '{context}'")
        ser = cursor.fetchone()
        emit('getalert',(room,m,email),to=ser['sid'])
        cursor.execute(f"select perfo from service where sid = %s",[ser['sid'],])
        per = cursor.fetchone()
        perfo = per['perfo']
        emit('message', {'msg': message['msg'],'utype':utype,'emotion':1,'id':str(uuid.uuid1()),'performance':perfo},to = room,namespace="/chat")

    else:
        emit('message', {'msg': message['msg'],'utype':utype,'emotion':1,'id':str(uuid.uuid1()),'performance':message['performance']},to = room,namespace="/chat")


app.run('0.0.0.0',port=2003,debug=True)
socketio.run(app)