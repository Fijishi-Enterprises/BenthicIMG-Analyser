from django.conf import settings


def help_links(request):
    return dict(
        account_questions_link=settings.ACCOUNT_QUESTIONS_LINK,
        forum_link=settings.FORUM_LINK,
    )
