from django.test import SimpleTestCase

from services.image_urls import (
    build_service_image_url,
    get_service_image_filename,
    get_service_image_url,
)


class ServiceImageUrlTests(SimpleTestCase):
    def test_maps_service_names_to_public_image_files(self):
        self.assertEqual(
            get_service_image_filename("4 x 6 Duvet cleaning"),
            "4×6 Duvet Cleaning.png",
        )
        self.assertEqual(
            get_service_image_filename("Storage Services"),
            "Storage.png",
        )
        self.assertEqual(
            get_service_image_filename("Bedsitter Fumigation(Primary)"),
            "Bedsitter Fumigation.png",
        )
        self.assertEqual(
            get_service_image_filename("Clean Now Pay Later Laundry / KG"),
            "Clean Now Pay Later.png",
        )
        self.assertIsNone(get_service_image_filename("Unrelated service"))
        self.assertEqual(
            get_service_image_url("Standard Wash"),
            "https://wildwash-images.s3.eu-north-1.amazonaws.com/images/"
            "Standard%20Wash.png",
        )

    def test_builds_encoded_aws_url_for_filename(self):
        self.assertEqual(
            build_service_image_url(
                "https://wildwash-images.s3.eu-north-1.amazonaws.com/images/",
                "4×6 Duvet Cleaning.png",
            ),
            "https://wildwash-images.s3.eu-north-1.amazonaws.com/images/"
            "4%C3%976%20Duvet%20Cleaning.png",
        )
