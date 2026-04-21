# app/services/employer_service.py

from app.repository.employer_repository import EmployerRepository
from app.models.employer_model import Employer    

repo = EmployerRepository()


def get_all_employers():
    rows = repo.fetch_all()

    # convert DB rows → model objects
    employers = [Employer(
        id=row['id'],   
        first_name=row['firstName'],
        last_name=row['lastName'],
        email=row['email'],
        phone=row['phone'],
        verified=bool(row.get('verified', 0))
    ).to_dict() for row in rows]

    return employers


def get_employer_by_id(employer_id):
    row = repo.fetch_by_id(employer_id)

    if not row:
        return {"error": "Employer not found"}, 404

    employer = Employer(
        id=row['id'],   
        first_name=row['firstName'],
        last_name=row['lastName'],
        email=row['email'],
        phone=row['phone'],
        verified=bool(row.get('verified', 0))
    )

    return employer.to_dict()


def create_employer(data):
    # basic validation
    required_fields = ["firstName", "email"]
    for field in required_fields:
        if field not in data:
            return {"error": f"{field} is required"}, 400

    employer_id = repo.insert(data)

    return {
        "message": "Employer created",
        "id": employer_id
    }


def update_employer(employer_id, data):
    updated = repo.update(employer_id, data)

    if not updated:
        return {"error": "Employer not found"}, 404

    return {"message": "Employer updated"}


def delete_employer(employer_id):
    deleted = repo.delete(employer_id)

    if not deleted:
        return {"error": "Employer not found"}, 404

    return {"message": "Employer deleted"}

def get_employer_by_email(email):
    row = repo.fetch_by_email(email)

    if not row:
        return {"error": "Employer not found"}, 404

    employer = Employer(
        id=row['id'],   
        first_name=row['firstName'],
        last_name=row['lastName'],
        email=row['email'],
        phone=row['phone'],
        verified=bool(row.get('verified', 0))
    )

    return employer.to_dict()


def set_employer_verified_status(employer_id, verified=True):
    updated = repo.set_verified_status(employer_id, verified)

    if not updated:
        return {"error": "Employer not found"}, 404

    return {"message": "Employer verification status updated", "verified": bool(verified)}
