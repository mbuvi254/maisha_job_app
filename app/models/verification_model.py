class Verification:
    def __init__(self, id=None, user_email=None, otp=None, created_at=None):
        self.id = id
        self.user_email = user_email
        self.otp = otp
        self.created_at = created_at

    def to_dict(self):
        return {
            "id": self.id,
            "user_email": self.user_email,
            "otp": self.otp,
            "created_at": self.created_at
        }
