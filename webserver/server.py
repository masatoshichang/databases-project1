#!/usr/bin/env python2.7

"""
Columbia W4111 Intro to databases
Example webserver

To run locally

    python server.py

Go to http://localhost:8111 in your browser


A debugger such as "pdb" may be helpful for debugging.
Read about it online.
"""

import os
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import Flask, request, render_template, g, redirect, Response, session, jsonify
import json
from random import randint
import datetime

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)

DATABASEURI = "postgresql://mc4235:ku6z3@104.196.175.120/postgres"

engine = create_engine(DATABASEURI)

@app.before_request
def before_request():
  """
  This function is run at the beginning of every web request
  (every time you enter an address in the web browser).
  We use it to setup a database connection that can be used throughout the request

  The variable g is globally accessible
  """
  try:
    g.conn = engine.connect()
  except:
    print "uh oh, problem connecting to database\n\n\n\n\n\n"
    import traceback; traceback.print_exc()
    g.conn = None

@app.teardown_request
def teardown_request(exception):
    """
    At the end of the web request, this makes sure to close the database connection.
    If you don't the database could run out of memory!
    """
    try:
        g.conn.close()
    except Exception as e:
        pass

def redirect_url():
    return request.referrer or '/'

def logged():
    name = None
    if 'uid' in session:
        cursor = g.conn.execute('select name from users where uid=%s', (session['uid'],))
        name = list(cursor)[0][0]
    return name

@app.route('/')
def index():
  login_name = logged()
  is_user_admin = is_admin()
  context = dict(login_name = login_name, is_admin = is_user_admin)
  return render_template("index.html", **context)

@app.route('/registration', methods=['GET'])
def register():
    if 'uid' in session:
        return redirect_url()
    else:
        return render_template("register.html")

@app.route('/registered', methods=['POST'])
def registered():
    email = request.form['email']
    password = request.form['pass']
    username = request.form['username']
    dob = request.form['dob']
    cursor = g.conn.execute("SELECT 1 FROM users WHERE email = %s", (email));
    row = cursor.fetchone()
    msg = "User with email {} has already existed. Please login instead.".format(email)
    err = False
    if not row:
        msg = ""
    if password == "":
        msg = msg + "\n Empty password."
        err = True
    if email == "":
        msg = msg + "\n Empty email."
        err = True
    if username == "":
        msg = msg + "\n Empty user name."
        err = True
    if len(dob) > 10:
        msg = msg +"\n invalid birth date."
        err =True
    content = dict(error_msg = msg)

    if row or err:
        return render_template("register.html", **content)
    cursor = g.conn.execute("INSERT INTO users(email, name, dob, password) VALUES (%s, %s, %s, %s)", (email, username, dob, password))
    if cursor:
        cursor = g.conn.execute("SELECT uid FROM users WHERE email=%s;", email)
        uid = list(cursor)[0][0]
        session['uid'] = uid
        g.conn.execute("INSERT INTO consumer(cid) VALUES (%s)", (uid))
        return redirect('/')
    else:
        msg = "something is wrong with db"
        content["error_msg"] =  msg
        return render_template("register.html", **content)

@app.route('/users')
def show_users():
    cursor = g.conn.execute("SELECT uid, name, email FROM users")
    users = []
    for result in cursor:
        dict_user = {'uid': result['uid'], 'name': result['name'], 'email': result['email']}
        users.append(dict_user)
    cursor.close()
    print(users)

    context = dict(data = users)

    return render_template("user_list.html", **context)

@app.route('/login_page')
def show_login_page():
    if 'uid' in session:
        return redirect(redirect_url())
    return render_template('login_page.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'uid' in session:
        return render_template('index.html', **context)
    elif request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        cursor = g.conn.execute("SELECT EXISTS(SELECT 1 FROM users WHERE email=%s and password=%s);", (email, password))

        is_exists = list(cursor)[0][0]
        if is_exists:
            cursor = g.conn.execute("SELECT uid FROM users WHERE email=%s;", email)
            session['uid'] = list(cursor)[0][0]
        else:
            context = dict(error_msg = 'Login credentials do not exist. Please try again.')
            return render_template("login_page.html", **context)
    else:
        pass
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('uid', None)
    return redirect('/')

@app.route('/product')
def product():
    login_name = logged()
    is_user_admin = is_admin()
    cursor = g.conn.execute('SELECT * FROM product;')
    result = cursor.fetchall()
    num_prod = len(result)
    cursor = g.conn.execute('SELECT name FROM category;');
    tag_list = cursor.fetchall()
    context = dict(product_list = result, num_products = num_prod, login_name = login_name, is_admin = is_user_admin, tag_list = tag_list)
    return render_template('product.html', **context)

@app.route('/refine_product', methods = ['POST'])
def refine_product():
    tag_sel = request.form.getlist('tags')
    login_name = logged()
    is_user_admin = is_admin()

    if len(tag_sel) == 0:
        return redirect('/product')
    cmd = "SELECT cat_id FROM category WHERE name=%s"
    cmd2 = "SELECT name FROM category WHERE name=%s"
    for idx, tag in enumerate(tag_sel):
        if idx == 0:
            continue
        else:
            cmd2 = cmd2+' or name = %s'
            cmd = cmd+' or name = %s'

    n_cmd = 'WITH t1 AS ( '+ cmd +' ) SELECT * FROM product WHERE NOT EXISTS (SELECT cat_id FROM t1 WHERE NOT EXISTS (SELECT B.cat_id FROM belonging AS B WHERE product.pid = B.pid AND B.cat_id = t1.cat_id));'
    args = tuple(tag_sel)
    cursor = g.conn.execute(n_cmd, args)
    result = cursor.fetchall()
    cursor = g.conn.execute('SELECT name FROM category;');
    tag_list = cursor.fetchall()
    cursor = g.conn.execute(cmd2, args)
    tag_sel = cursor.fetchall()
    context = dict(product_list = result, login_name = login_name, is_admin = is_user_admin, tag_list = tag_list, tag_sel = tag_sel)
    return render_template('product.html', **context)


@app.route('/product/<pid>')
def product_page(pid):
    login_name = logged()
    is_user_admin = is_admin()

    cursor = g.conn.execute('SELECT * FROM product WHERE pid=%s;', (pid))
    result = cursor.fetchone()
    if result is None:
        print('Product for pid {} does not exist'.format(pid))
        return redirect('/product')
    context = dict(product_id = pid, product_name = result['name'], product_price = result['price'], product_description = result['description'], product_rating = result['rating'], product_quantity = result['quantity'], login_name = login_name, is_admin = is_user_admin)
    return render_template('single_product.html', **context)

def get_addr_list(uid):
    cursor = g.conn.execute('SELECT a.add_id, a.name, a.street_info, a.city, a.state, a.zip FROM address a, addressmaintenance am, users u, consumer c  WHERE u.uid=%s and u.uid=c.cid  and c.cid=am.cid and a.add_id=am.add_id;', (uid))
    result = list(cursor)
    addr_list = []
    for addr in result:
        addr_list.append({'add_id': addr[0], 'name': addr[1], 'street_info': addr[2], 'city': addr[3], 'state': addr[4], 'zip': repr(addr[5])})
    return addr_list

@app.route('/purchase_product/<pid>')
def purchase_product(pid):
    if not ('uid' in session):
        return redirect('/login_page')
    login_name = logged()
    is_user_admin = is_admin()

    cursor = g.conn.execute('SELECT name FROM product where pid=%s;', (pid))
    result = list(cursor)
    prod_name = result[0][0]

    uid = session['uid']
    addr_list = get_addr_list(uid)

    context = dict(product_id = pid, product_name = prod_name, address_list = addr_list, login_name = login_name, is_admin = is_user_admin)

    return render_template('purchase_page.html', **context)

@app.route('/purchase', methods=['POST'])
def purchase():
    print request.form
    which_address = request.form['select_addr']
    pid = request.form['pid']
    pname = request.form['pname']
    uid = session['uid']
    addr_list = get_addr_list(uid)
    login_name = logged()
    context = dict(product_id = pid, product_name = pname, address_list = addr_list, login_name = login_name)
    chosen = None
    err = False
    add_id = '-1'
    bill_info = ''

    if which_address == 'existing_addr':
        chosen = request.form['recipient_addr_id']
    else:
        r_name = request.form['recipient_name']
        r_street = request.form['recipient_street']
        r_city = request.form['recipient_city']
        r_state = request.form['recipient_state']
        r_zip = request.form['recipient_zip']
        if len(r_name) <3 or len(r_name) >40 or len(r_street) < 3 or len(r_state)==0 or len(r_city) > 30 or len(r_city) == 0 or len(r_zip) <4 or len(r_state) > 3 :
            err = True
        try:
            int(r_zip)
        except (ValueError, TypeError):
            err = True

    if chosen == '-1' or err:
        error_msg = "Sorry invalid address selection!"
        context['error_msg'] = error_msg
        return render_template('purchase_page.html', **context)
    elif len(request.form['cc']) == 0 or len(request.form['cvv']) == 0 or len(request.form['ed']) == 0:
        error_msg = "Sorry invalid billing info!"
        context['error_msg'] = error_msg
        return render_template('purchase_page.html', **context)
    else:
        bill_info = bill_info+'Credit Card No.: ' + request.form['cc']+' CVV: ' +request.form['cvv']+' Expiration Date: '+request.form['ed']
    if which_address == 'new_addr':
        cmd = 'INSERT INTO address(name, street_info, city, state, zip) VALUES (%s, %s, %s, %s, %s)'
        add_data = (r_name, r_street, r_city, r_state, r_zip)
        cursor = g.conn.execute(cmd, add_data)
        cmd = 'SELECT add_id FROM address WHERE name = %s AND street_info = %s and city= %s and state = %s and zip=%s'
        cursor = g.conn.execute(cmd, add_data)
        add_id = list(cursor)[0][0]
        cursor = g.conn.execute('SELECT 1 FROM addressmaintenance WHERE cid = %s and add_id = %s', (uid, add_id))
        if len(list(cursor)) == 0:
            g.conn.execute('INSERT INTO addressmaintenance(cid, add_id) VALUES (%s, %s)', (uid, add_id))
    if(add_id == '-1'):
        add_id = chosen
    try:
        int(add_id)
    except (ValueError, TypeError):
        error_msg = "Sorry your address is not valid!"
        context['error_msg'] = error_msg
        return render_template('purchase_page.html', **context)

    cursor = g.conn.execute('SELECT order_id FROM orders ORDER BY order_id DESC ')
    order_id = 1
    res = cursor.first()
    if res != None:
        try:
            order_id = int(res[0]) + 1
        except (ValueError, TypeError):
            error_msg = "something is wrong!"
            context['error_msg'] = error_msg
            return render_template('purchase_page.html', **context)
    cursor = g.conn.execute('SELECT admin_id FROM administrator ORDER BY admin_id DESC ')
    admax = int(cursor.first()[0])
    admini = 11
    admin_id = randint(admini, admax)
    cursor = g.conn.execute('SELECT price, quantity FROM product WHERE pid = %s', (pid))
    res = cursor.first()
    amount = res[0]
    quantity = res[1]
    if quantity == '0':
        context['error_msg'] = 'Sorry this product is completely sold out.'
        return render_template('purchase_page.html', **context)
    else:
        quantity = int(quantity)
        quantity = quantity - 1
        cursor = g.conn.execute('UPDATE product SET quantity = %s WHERE pid = %s', (quantity, pid))
    date = datetime.datetime.now().date()
    time = datetime.datetime.now().time()
    cmd = 'INSERT INTO orders(order_id, billing_info, amount, shipadd_id, cid, admin_id, order_date, order_time) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)'
    new_order = (order_id, bill_info, amount, add_id, uid, admin_id, date, time)
    cursor = g.conn.execute(cmd, new_order)
    cursor = g.conn.execute('INSERT INTO orderContains(order_id, pid, product_quantity) VALUES (%s, %s, %s)', (order_id, pid, 1))

    cursor = g.conn.execute('SELECT name, street_info, city, state, zip FROM address WHERE add_id = %s', (add_id))
    add_data = cursor.first()
    r_name = add_data[0]
    r_street = add_data[1]
    r_city = add_data[2]
    r_state = add_data[3]
    r_zip = add_data[4]
    context = dict(product_id = pid, product_name = pname, address_list = addr_list, login_name = login_name, r_name = r_name, r_street= r_street, r_city=r_city,r_state=r_state,r_zip=r_zip, bill_info = bill_info)
    return render_template('order_confirm.html', **context)


def is_admin(uid=None):
    is_admin = False
    if uid is None and 'uid' in session:
        uid = session['uid']

    cursor = g.conn.execute("SELECT EXISTS(SELECT 1 FROM administrator a WHERE a.admin_id=%s);", (uid,))
    result = cursor.fetchone()[0]
    return result


@app.route('/admin')
def admin_page():
    login_name = logged()
    is_user_admin = is_admin()

    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')

    cursor = g.conn.execute('SELECT p.name, u.name, u.uid FROM product p, productoversee po, users u WHERE p.pid=po.pid and po.admin_id=u.uid;')

    list_products = []
    for result in list(cursor):
        you_manage = False
        if result[2] == uid:
            you_manage = True
        list_products.append({'product_name': result[0], 'managed_by': result[1], 'you_manage': you_manage})

    cursor = g.conn.execute('SELECT c.name, u.name, u.uid FROM category c, categorymanagement cm, users u WHERE c.cat_id=cm.cat_id and cm.admin_id=u.uid;')

    list_categories = []
    for result in list(cursor):
        you_manage = False
        if result[2] == uid:
            you_manage = True

        list_categories.append({'category_name': result[0], 'managed_by': result[1], 'you_manage': you_manage})


    context = dict(login_name = login_name, is_admin = is_user_admin, list_products=list_products, list_categories=list_categories)
    return render_template('admin_page.html', **context)

@app.route('/admin/add_product_page')
def admin_add_product():
    login_name = logged()
    is_user_admin = is_admin()

    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')

    cursor = g.conn.execute('SELECT cat_id, name, description FROM category;')
    results = list(cursor)
    category_list = []
    for cat in results:
        category_list.append({'cat_id': cat[0], 'name': cat[1]})

    context = dict(cat_list = category_list, login_name = login_name, is_admin = is_user_admin)

    return render_template('admin_add_product.html', **context)


@app.route('/admin/add_product', methods=['POST'])
def add_product():
    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')

    name = request.form['name']
    description = request.form['description']
    quantity = request.form['quantity']
    price = request.form['price']
    pic_address = request.form['pic_address']
    cat_id = request.form['category']

    cursor = g.conn.execute('SELECT max(pid) FROM product;')
    result = list(cursor)
    pid = result[0][0] + 1

    cursor = g.conn.execute('INSERT INTO product VALUES (%s, %s, %s, %s, %s, %s, %s);', (pid, price, description, quantity, name, 3,  pic_address))

    g.conn.execute('INSERT INTO belonging VALUES (%s, %s);', (cat_id, pid))

    g.conn.execute('INSERT INTO productoversee VALUES (%s, %s);', (pid, uid))

    return redirect('/admin')

@app.route('/admin/remove_product_page')
def remove_product_page():
    login_name = logged()
    is_user_admin = is_admin()

    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')

    cursor = g.conn.execute('SELECT * FROM product;')
    results = list(cursor)

    product_list = []
    for prod in results:
        product_list.append({'pid': prod[0], 'price': prod[1], 'description': prod[2], 'quantity': prod[3], 'name': prod[4], 'rating': prod[5]})

    context = dict(prod_list = product_list, login_name = login_name, is_admin = is_user_admin)

    return render_template('admin_remove_product.html', **context)

@app.route('/admin/remove_product', methods=['POST'])
def remove_product():

    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')

    pid = request.form['pid']

    cursor = g.conn.execute('DELETE FROM belonging WHERE pid=%s;', (pid,))
    cursor = g.conn.execute('DELETE FROM productoversee WHERE pid=%s;', (pid,))
    cursor = g.conn.execute('DELETE FROM product WHERE pid=%s;', (pid,))

    return redirect('/admin')

@app.route('/admin/edit_product_page')
def edit_product_page():
    login_name = logged()
    is_user_admin = is_admin()

    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')

    cursor = g.conn.execute('SELECT * FROM product;')
    results = list(cursor)

    product_list = []
    for prod in results:
        product_list.append({'pid': prod[0], 'price': prod[1], 'description': prod[2], 'quantity': prod[3], 'name': prod[4], 'rating': prod[5]})

    context = dict(prod_list = product_list, login_name = login_name, is_admin = is_user_admin)

    return render_template('edit_product_page.html', **context)

@app.route('/admin/edit_product', methods=['POST'])
def edit_product():
    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')

    name = request.form['name']
    description = request.form['description']
    rating = request.form['rating']
    quantity = request.form['quantity']
    price = request.form['price']
    pic_address = request.form['pic_address']


    for strings in [name, description, rating, quantity, price, pic_address]:
        if len(strings.strip()) <= 0:
            context = dict(error_msg = 'Inputs should not be empty')
            return render_template('edit_product_page.html', **context)

    try:
        temp = float(price)
    except Exception:
        context = dict(error_msg = 'Price is not a valid number')
        return render_template('edit_product_page.html', **context)

    try:
        temp = int(quantity)
    except Exception:
        context = dict(error_msg = 'Quantity is not a valid number')
        return render_template('edit_product_page.html', **context)

    pid = request.form['pid']

    g.conn.execute('UPDATE product SET name=%s, description=%s, price=%s, quantity=%s, rating=%s, pic_address=%s WHERE pid=%s;', (name, description, price, quantity, rating, pic_address, pid))

    return redirect('/admin')

@app.route('/user_order')
def show_orders():
    if 'uid' not in session:
        context = dict(error_msg='Please login first.')
        return render_template('index.html', **context)
    uid = session['uid']
    cursor = g.conn.execute('WITH t1 AS (SELECT * FROM orders WHERE cid = %s), t2 AS (SELECT t1.order_id AS oid, count(*) AS item_amount FROM t1 INNER JOIN orderContains AS oc ON t1.order_id=oc.order_id GROUP BY oid) SELECT oid, item_amount, billing_info, amount, shipadd_id, order_date, order_time, ship_time, tracking_num FROM t2 JOIN t1 ON t1.order_id = t2.oid ORDER BY order_date DESC, order_time DESC;', (uid))
    result = cursor.fetchall()
    res = []
    for order in result:
        oid = order['oid']
        order_info = dict(order)
        prod = []
        cursor = g.conn.execute('SELECT * FROM address WHERE add_id = %s', order['shipadd_id'])
        ship_info = cursor.first()
        cursor = g.conn.execute('WITH t1 AS (SELECT * FROM orderContains WHERE order_id = %s) SELECT product.pid AS p_id, product_quantity, name, description, price FROM t1 JOIN product ON t1.pid = product.pid;', (oid))
        ps = cursor.fetchall()
        for p in ps:
            pd = dict(p)
            pd['pr'] = repr(pd['price'])
            prod.append(pd)
        order_info['products'] = prod
        order_info['ship_info'] = 'Name:' + ship_info['name'] + ' @ ' + ship_info['street_info'] + ' ' + ship_info['city'] + ' ' +ship_info['state']+' '+ repr(ship_info['zip'])
        res.append(order_info)
    login_name = logged()
    context = dict(order_list = res, login_name=login_name)
    return render_template('orders.html', **context)

@app.route('/add_book')
def get_addr():

    if 'uid' not in session:
        context = dict(error_msg='Please login first.')
        return render_template('index.html', **context)
    uid = session['uid']
    addr_list = get_addr_list(uid)
    login_name = logged()
    context = dict(login_name=login_name, address_list = addr_list)
    return render_template('add_manage.html', **context)

def valid_address(name, street_info, city, state, add_zip):
    error_msg = ""
    if len(name) <3 or len(name) >40:
        error_msg = error_msg+"Invalid name."
    elif len(street_info)<3:
        error_msg = error_msg+" Street info too short."
    elif len(state) == 0 or len(state)>3:
        error_msg = error_msg+" Invalid state (two-letter abbr only)."
    elif len(city) == 0:
        error_msg = error_msg+" Invalid city."
    elif len(add_zip) <4 or len(add_zip)>7:
        error_msg = error_msg+" Invalid zip."
    else:
        try:
            int(add_zip)
        except (ValueError, TypeError):
            error_msg = error_msg+" Zip must be numbers only."
    return error_msg

@app.route('/add_edit/<add_id>')
def edit_address(add_id):
    if not ('uid' in session):
        return redirect('/login_page')
    login_name = logged()
    cursor = g.conn.execute('SELECT * FROM address WHERE add_id = %s;', (add_id))
    add = cursor.first()

    context = dict(add)
    context['login_name'] = login_name
    return render_template('address_edit.html', **context)

@app.route('/add_edit_submit/<add_id>', methods=['POST'])
def add_edit_submit(add_id):
    if not ('uid' in session):
        return redirect('/login_page')
    login_name = logged()
    name = request.form['name']
    street_info = request.form['street']
    city = request.form['city']
    state = request.form['state']
    add_zip = request.form['zip']
    error_msg = valid_address(name, street_info, city, state, add_zip)
    context = dict(login_name=login_name, name = name, street_info = street_info, city = city, state = state, error_msg = error_msg, zip = add_zip)
    if error_msg != "":
        return render_template('address_edit.html', **context)
    g.conn.execute("UPDATE address SET name = %s, street_info=%s, city=%s, state = %s, zip=%s WHERE add_id = %s;", (name, street_info, city, state, add_zip, add_id))
    return redirect('/add_book')  # error address not found

@app.route('/add_add', methods=['POST'])
def add_add():
    if not ('uid' in session):
        return redirect('/login_page')
    login_name = logged()
    name = request.form['name']
    street_info = request.form['street']
    city = request.form['city']
    state = request.form['state']
    add_zip = request.form['zip']
    error_msg = valid_address(name, street_info, city, state, add_zip)
    context = dict(login_name=login_name, name = name, street_info = street_info, city = city, state = state, error_msg = error_msg, zip = add_zip)
    if error_msg != "":
        return render_template('address_add.html', **context)

    g.conn.execute("INSERT INTO address(name, street_info, city, state, zip) VALUES (%s, %s, %s, %s, %s)", (name, street_info, city, state, add_zip))

    uid=session['uid']
    cmd = 'SELECT add_id FROM address WHERE name = %s AND street_info = %s and city= %s and state = %s and zip=%s'
    cursor = g.conn.execute(cmd, (name, street_info, city, state, add_zip))
    add_id = list(cursor)[0][0]
    cursor = g.conn.execute('SELECT 1 FROM addressmaintenance WHERE cid = %s and add_id = %s', (uid, add_id))
    if len(list(cursor)) == 0:
        g.conn.execute('INSERT INTO addressmaintenance(cid, add_id) VALUES (%s, %s)', (uid, add_id))
    return redirect('/add_book')

@app.route('/add_delete/<add_id>')
def delete_add(add_id):
    if not ('uid' in session):
        return redirect('/login_page')
    login_name = logged()
    uid = session['uid']
    cursor = g.conn.execute('DELETE FROM addressMaintenance WHERE cid = %s and add_id = %s;', (uid, add_id))
    return redirect('/add_book')

@app.route('/admin/add_category_page')
def add_category_page():
    login_name = logged()
    is_user_admin = is_admin()

    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')


    context = dict(login_name = login_name, is_admin = is_user_admin)
    return render_template('add_category_page.html', **context)

@app.route('/admin/add_category', methods=['POST'])
def add_category():
    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')


    name = request.form['name']
    description = request.form['description']

    cursor = g.conn.execute('SELECT max(cat_id) FROM category;')
    result = list(cursor)
    cat_id = result[0][0] + 1

    cursor = g.conn.execute('INSERT INTO category VALUES (%s, %s, %s);', (cat_id, name, description))

    admin_id = session['uid']

    cursor = g.conn.execute('INSERT INTO categorymanagement VALUES (%s, %s);', (cat_id, admin_id))

    return redirect('/admin')

@app.route('/admin/remove_category_page')
def remove_category_page():
    login_name = logged()
    is_user_admin = is_admin()

    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')

    cursor = g.conn.execute('SELECT * FROM category c WHERE EXISTS( SELECT * FROM belonging b WHERE c.cat_id=b.cat_id);')
    print('Category with products')
    categories_with_products = []
    for result in list(cursor):
        categories_with_products.append({'cat_id': result[0], 'name': result[1], 'description': result[2]})
        print(result)

    cursor = g.conn.execute('SELECT * FROM category c WHERE NOT EXISTS( SELECT * FROM belonging b WHERE c.cat_id=b.cat_id);')
    print('Category without products')
    categories_without_products = []
    for result in list(cursor):
        categories_without_products.append({'cat_id': result[0], 'name': result[1], 'description': result[2]})
        print(result)


    context = dict(login_name = login_name, is_admin = is_user_admin, categories_with_products = categories_with_products, categories_without_products = categories_without_products)
    return render_template('remove_category_page.html', **context)


@app.route('/admin/remove_category', methods=['POST'])
def remove_category():
    if 'uid' not in session:
        return redirect('/')

    uid = session['uid']
    if not is_admin(uid):
        return redirect('/')

    cat_id = request.form['cat_id']

    # Check if we are allowed to delete the category
    cursor = g.conn.execute('SELECT EXISTS (SELECT 1 FROM category c WHERE NOT EXISTS( SELECT * FROM belonging b WHERE c.cat_id=%s and c.cat_id=b.cat_id));',(cat_id,))
    is_exists = list(cursor)[0][0]

    if not is_exists:
        print('You are not allowed to delete category {}'.format(cat_id))
        return redirect('/admin')


    cursor = g.conn.execute('DELETE FROM categorymanagement WHERE cat_id=%s;', (cat_id,))
    cursor = g.conn.execute('DELETE FROM category WHERE cat_id=%s;', (cat_id,))

    return redirect('/admin')

if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--debug', is_flag=True)
    @click.option('--threaded', is_flag=True)
    @click.argument('HOST', default='0.0.0.0')
    @click.argument('PORT', default=8111, type=int)
    def run(debug, threaded, host, port):
        """
        This function handles command line parameters.
        Run the server using

            python server.py

        Show the help text using

            python server.py --help

        """
        HOST, PORT = host, port
        print "running on %s:%d" % (HOST, PORT)
        app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

    app.secret_key = 'A0Zr98j/3yX R~XHH!jmN]LWX/,?RT'
    run()
