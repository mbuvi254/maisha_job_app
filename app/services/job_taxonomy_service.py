from app.repository.job_taxonomy_repository import JobTaxonomyRepository


repo = JobTaxonomyRepository()


def get_industries():
    return repo.fetch_industries()


def get_industry_by_id(industry_id):
    if not industry_id:
        return None
    return repo.fetch_industry_by_id(industry_id)


def get_categories(industry_id=None):
    return repo.fetch_categories(industry_id)


def get_category_by_id(category_id):
    if not category_id:
        return None
    return repo.fetch_category_by_id(category_id)


def get_grouped_categories(industry_id=None):
    industries = get_industries()
    categories = get_categories(industry_id)
    grouped = []

    for industry in industries:
        grouped.append({
            "industry": industry,
            "categories": [
                category
                for category in categories
                if str(category.get("industry_id")) == str(industry.get("id"))
            ],
        })

    return grouped


def create_industry(name):
    if not name:
        return {"error": "Industry name is required"}, 400

    name = name.strip()
    if not name:
        return {"error": "Industry name is required"}, 400

    existing = next((industry for industry in get_industries() if industry.get("name", "").lower() == name.lower()), None)
    if existing:
        return {"error": "Industry already exists"}, 400

    industry_id = repo.insert_industry(name)
    return {"message": "Industry created", "id": industry_id}


def update_industry(industry_id, name):
    if not industry_id or not name:
        return {"error": "Industry id and name are required"}, 400

    updated = repo.update_industry(industry_id, name.strip())
    if not updated:
        return {"error": "Industry not found"}, 404

    return {"message": "Industry updated", "id": industry_id}


def delete_industry(industry_id):
    if not industry_id:
        return {"error": "Industry id is required"}, 400

    deleted = repo.delete_industry(industry_id)
    if not deleted:
        return {"error": "Industry not found"}, 404

    return {"message": "Industry deleted"}


def create_category(industry_id, name):
    if not industry_id or not name:
        return {"error": "Industry and category name are required"}, 400

    name = name.strip()
    if not name:
        return {"error": "Category name is required"}, 400

    industry = get_industry_by_id(industry_id)
    if not industry:
        return {"error": "Industry not found"}, 404

    existing = next(
        (
            category
            for category in get_categories()
            if str(category.get("industry_id")) == str(industry_id) and category.get("name", "").lower() == name.lower()
        ),
        None,
    )
    if existing:
        return {"error": "Category already exists in this industry"}, 400

    category_id = repo.insert_category(industry_id, name)
    return {"message": "Category created", "id": category_id}


def update_category(category_id, industry_id, name):
    if not category_id or not industry_id or not name:
        return {"error": "Category id, industry id and name are required"}, 400

    category = get_category_by_id(category_id)
    if not category:
        return {"error": "Category not found"}, 404

    industry = get_industry_by_id(industry_id)
    if not industry:
        return {"error": "Industry not found"}, 404

    updated = repo.update_category(category_id, industry_id, name.strip())
    if not updated:
        return {"error": "Category not found"}, 404

    return {"message": "Category updated", "id": category_id}


def delete_category(category_id):
    if not category_id:
        return {"error": "Category id is required"}, 400

    deleted = repo.delete_category(category_id)
    if not deleted:
        return {"error": "Category not found"}, 404

    return {"message": "Category deleted"}
