"""Public recovery pages and root-scoped PWA service worker."""
from flask import Blueprint, current_app, jsonify, render_template, request, send_from_directory
from werkzeug.exceptions import default_exceptions

system_bp = Blueprint('system_bp', __name__)
ERROR_PAGES = {
    400: ('Check your request', 'The request could not be processed. Check your entries or reload the form and try again.'),
    401: ('Please sign in', 'Sign in to your account to continue.'),
    403: ('Access restricted', 'Your account does not have permission to open this page.'),
    404: ('This page could not be found', 'The link may have changed, or this page is no longer available.'),
    405: ('This action is not available', 'Open the page using its normal link and try again.'),
    410: ('This item is no longer available', 'The requested item is no longer available. Return to the previous page for your next steps.'),
    413: ('This upload is too large', 'Choose a smaller file and try uploading it again.'),
    429: ('Please slow down', 'Too many requests were made. Wait a little before trying again.'),
    500: ('Something went wrong', 'We could not complete your request. Please try again in a moment.'),
    502: ('A service is unavailable', 'A supporting service is not responding. Please try again shortly.'),
    503: ('Temporarily unavailable', 'The service is temporarily unavailable. Please try again shortly.'),
    504: ('The request took too long', 'A supporting service took too long to respond. Please try again.'),
}


def error_response(error):
    code = error.code or 500
    title, message = ERROR_PAGES.get(code, ERROR_PAGES[500])
    if code < 500 and error.description != default_exceptions[code].description:
        message = error.description
    response = error.get_response()
    if request.is_json or request.path.startswith('/api/') or request.accept_mimetypes['application/json'] > request.accept_mimetypes['text/html']:
        response.set_data(current_app.json.dumps({'error': message, 'status': code}))
        response.content_type = 'application/json'
    else:
        response.set_data(render_template('errors/error.html', code=code, title=title, message=message))
        response.content_type = 'text/html; charset=utf-8'
    response.headers['Cache-Control'] = 'no-store'
    return response


@system_bp.get('/errors/<int:code>')
def error_page(code):
    from flask import abort
    if code not in ERROR_PAGES:
        abort(404)
    return error_response(default_exceptions[code]())


@system_bp.get('/offline')
def offline():
    return render_template('errors/offline.html')


@system_bp.get('/service-worker.js')
def service_worker():
    response = send_from_directory(current_app.static_folder, 'pwa/sw.js', mimetype='application/javascript')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Service-Worker-Allowed'] = '/'
    return response


def register_error_handlers(app):
    for code in ERROR_PAGES:
        app.register_error_handler(code, error_response)
