from flask import Flask, request, render_template, g, redirect, Response, session, jsonify
from flask_login import (LoginManager, login_required, login_user, current_user, logout_user, UserMixin)

class User(UserMixin):
    def __init__(self, uid, password):
        self.uid = uid
        self.password = password

    def get_auth_token(self):
        data = [str(self.id), self.password]
        return login_serializer.dumps(data)

    @staticmethod
    def get(email, password):
        cursor = g.conn.execute("SELECT EXISTS(SELECT 1 FROM users WHERE email=%s and password=%s);", (email, password))
        is_exists = list(cursor)[0][0]

        if is_exists:
            cursor = g.conn.execute("SELECT uid, password FROM users WHERE email=%s;", email)
            result = list(cursor)[0]
            uid = result[0]
            password = result[1]
            return User(uid, password)

        return None

