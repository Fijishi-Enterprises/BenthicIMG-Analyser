import datetime

from django_migration_testcase import MigrationTest


class EntriesToPostsMigrationTest(MigrationTest):

    before = [('blog', '0002_add_blogpost')]
    after = [('blog', '0003_port_entries_to_blogposts')]

    def test_migration(self):
        Entry = self.get_model_before('blog.Entry')
        User = self.get_model_before('auth.User')

        user = User.objects.create(
            username='testUser', first_name="Test", last_name="User")

        # Create Entries
        entry = Entry(
            title="Post 1",
            slug='post-1',
            content="Content goes here",
            # Published
            is_published=True,
            published_timestamp=datetime.datetime(
                2021, 4, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
            author=user,
            preview_content="Preview content goes here",
        )
        entry.save()
        entry = Entry(
            title="Post 2",
            slug='post-2',
            # Has an image path to convert
            content="An image: [Alt text](/media/andablog/images/2.png)",
            # Not published
            is_published=False,
            published_timestamp=None,
            author=user,
            preview_content="Preview content goes here",
        )
        entry.save()

        self.run_migration()

        BlogPost = self.get_model_after('blog.BlogPost')

        # Check the converted BlogPosts

        post_1 = BlogPost.objects.get(title="Post 1")
        self.assertEqual(post_1.slug, 'post-1')
        self.assertEqual(post_1.author, "Test User")
        self.assertEqual(post_1.content, "Content goes here")
        self.assertEqual(post_1.preview_content, "Preview content goes here")
        self.assertEqual(post_1.is_published, True)
        self.assertEqual(
            post_1.published_timestamp,
            datetime.datetime(
                2021, 4, 1, 0, 0, 0, tzinfo=datetime.timezone.utc))

        post_2 = BlogPost.objects.get(title="Post 2")
        self.assertEqual(
            post_2.content,
            "An image: [Alt text](/media/article_images/2.png)")
        self.assertEqual(post_2.is_published, False)
        self.assertEqual(post_2.published_timestamp, None)


class PostsToEntriesMigrationTest(MigrationTest):

    before = [('blog', '0003_port_entries_to_blogposts')]
    after = [('blog', '0001_initial')]

    def test_migration(self):
        BlogPost = self.get_model_before('blog.BlogPost')

        # Create BlogPosts
        post = BlogPost(
            title="Post 1",
            slug='post-1',
            author="Test User",
            content="Content goes here",
            preview_content="Preview content goes here",
            # Published
            is_published=True,
            published_timestamp=datetime.datetime(
                2021, 4, 1, 0, 0, 0, tzinfo=datetime.timezone.utc),
        )
        post.save()
        post = BlogPost(
            title="Post 2",
            slug='post-2',
            author="Test User",
            # Has an image path to convert
            content="An image: [Alt text](/media/article_images/2.png)",
            preview_content="Preview content goes here",
            # Not published
            is_published=False,
            published_timestamp=None,
        )
        post.save()

        self.run_migration()

        Entry = self.get_model_after('blog.Entry')

        # Check the converted Entries

        entry_1 = Entry.objects.get(title="Post 1")
        self.assertEqual(entry_1.slug, 'post-1')
        self.assertEqual(entry_1.author, None)
        self.assertEqual(entry_1.content.raw, "Content goes here")
        self.assertEqual(
            entry_1.preview_content.raw, "Preview content goes here")
        self.assertEqual(entry_1.is_published, True)
        self.assertEqual(
            entry_1.published_timestamp,
            datetime.datetime(
                2021, 4, 1, 0, 0, 0, tzinfo=datetime.timezone.utc))

        entry_2 = Entry.objects.get(title="Post 2")
        self.assertEqual(
            entry_2.content.raw,
            "An image: [Alt text](/media/andablog/images/2.png)")
        self.assertEqual(entry_2.is_published, False)
        self.assertEqual(entry_2.published_timestamp, None)
