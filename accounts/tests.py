from django.test import TestCase
from django.contrib.auth.models import User
from accounts.models import UserProfile
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

class ProfileViewTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123', email='test@example.com')
        self.profile = UserProfile.objects.create(user=self.user)
        # Create a mock file
        self.profile.profile_photo = SimpleUploadedFile(
            name='test_avatar.jpg',
            content=b'dummy_image_data',
            content_type='image/jpeg'
        )
        self.profile.save()

    def test_remove_photo(self):
        # Log in the user
        self.client.login(username='testuser', password='password123')
        
        # Verify photo exists initially
        self.assertTrue(bool(self.profile.profile_photo))
        
        # Submit the form with both update_profile and remove_photo (reproducing the UI form behavior)
        response = self.client.post(reverse('profile'), {
            'update_profile': '1',
            'remove_photo': '1',
            'first_name': 'Test',
            'last_name': 'User'
        })
        
        # Reload profile from db
        self.profile.refresh_from_db()
        
        # Check that the photo is removed
        self.assertFalse(bool(self.profile.profile_photo))
        
        # Verify success message is in the context
        self.assertIn("Profile photo removed successfully!", response.context['success'])
