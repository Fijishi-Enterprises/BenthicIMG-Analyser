import multiprocessing

bind = '127.0.0.1:8001'

# Number of worker processes
workers = multiprocessing.cpu_count()
# User and group for worker processes
user = 'www-data'
group = 'www-data'

# Request timeout.
#
# Note that nginx also has a request timeout, called proxy_read_timeout.
# If gunicorn times out, the browser gets a "502 Bad Gateway" page.
# If nginx times out, the browser gets a "504 Gateway Time-out" page.
#
# We'll make the gunicorn and nginx timeouts similar but slightly different,
# so that the timeout error is consistent (either always nginx or always
# gunicorn, not one or the other).
# In the meantime, the point in having two different timeouts is just to
# have a failsafe.
timeout = 604810
