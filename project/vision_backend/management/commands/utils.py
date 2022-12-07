from django.utils import timezone


def log(message, filename, write_command):
    """ logs message to file """
    now = timezone.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    with open(filename, 'a', encoding='utf-8') as fp:
        message_with_time = "[{}]: {}".format(dt_string, message)
        write_command(message_with_time)
        fp.write(message_with_time + '\n')
