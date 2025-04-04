from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, DateField, SelectField, SubmitField
from wtforms.validators import DataRequired

class InventoryItemForm(FlaskForm):
    category = SelectField('Choose Category', choices=[
        ('Medical Drugs', 'Medical Drugs'),
        ('Medical Equipments', 'Medical Equipments'),
        ('Pharmaceuticals', 'Pharmaceuticals')
    ], validators=[DataRequired()])
    name = StringField('Name', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired()])
    expiry_date = DateField('Expiry Date', format='%Y-%m-%d', validators=[DataRequired()])
    submit = SubmitField('Add Item')