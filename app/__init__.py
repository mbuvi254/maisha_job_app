from flask import Flask
from .blueprints import register_blueprints
from flask_mail import Mail
import os
from dotenv import load_dotenv


load_dotenv()

app=Flask(__name__)
register_blueprints(app)

app.secret_key=os.getenv('FLASK_SECRET_KEY')
  
    
   
# # Flask-Mail configuration
app.config['MAIL_SERVER'] = 'mail.cm.co.ke' 
app.config['MAIL_PORT'] = 587                
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False         
app.config['MAIL_USERNAME'] = 'accounts@cm.co.ke'
app.config['MAIL_PASSWORD'] = '2025Cybermaisha@'
app.config['MAIL_DEFAULT_SENDER'] = 'mail.cm.co.ke'

mail = Mail(app)
