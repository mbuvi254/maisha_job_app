# app/models/employer.py

class Employer:
    def __init__(self, id=None, first_name=None, last_name=None, email=None, phone=None, verified=None):
        self.id = id
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.phone = phone
        self.verified = verified

    def to_dict(self):
        return {
            "id": self.id,
            "firstName": self.first_name,
            "lastName": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "verified": self.verified
        }
