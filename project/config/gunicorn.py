import multiprocessing

# nginx should pass Django requests to here.
bind = '127.0.0.1:8001'

# Number of worker processes
workers = multiprocessing.cpu_count()

# Request timeout.
# Make this long enough to support:
# - Export statistics, annotations
# - Show statistics
# - Image upload
#
# Note that nginx also has a request timeout, called proxy_read_timeout.
# If gunicorn times out, the browser gets a "502 Bad Gateway" page.
# If nginx times out, the browser gets a "504 Gateway Time-out" page.
#
# We have to specify both timeout periods simply because the defaults
# for both are too low.
#
# We'll make the gunicorn and nginx timeouts similar but slightly different,
# so that the timeout error is consistent (either always nginx or always
# gunicorn, not one or the other).
timeout = 604810
