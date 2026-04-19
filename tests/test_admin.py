import pytest
import sys
from PyQt5.QtWidgets import QApplication
from pages.admin_page import CreateUserDialog, RegisterApartmentDialog

# PyQt requires a QApplication instance before any QWidget can be instantiated.
@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    yield app

def test_tc_a02_create_user_short_password(qapp):
    """TC-A02: Admin creates user with password shorter than required length."""
    dialog = CreateUserDialog("Bristol")
    dialog.username_input.setText("admin_test")
    dialog.first_name_input.setText("Test")
    dialog.last_name_input.setText("User")
    dialog.email_input.setText("test@pams.co.uk")
    dialog.password_input.setText("123")  # Short password (less than 6 chars)
    
    assert dialog.get_data() is None

def test_tc_a03_create_user_empty_fields(qapp):
    """TC-A03: Admin creates user without entering required fields."""
    dialog = CreateUserDialog("Bristol")
    # By default, inputs are empty. Let's ensure they are empty.
    dialog.username_input.setText("")
    dialog.password_input.setText("")
    
    assert dialog.get_data() is None

def test_tc_a09_register_apartment_empty_field(qapp):
    """TC-A09: Admin registers an apartment with empty field."""
    dialog = RegisterApartmentDialog("Bristol")
    # Leaving floor and rent empty will raise a ValueError when converting to int/float.
    dialog.floor.setText("")
    dialog.rent.setText("")
    
    assert dialog.get_data() is None

def test_tc_a11_register_apartment_no_type(qapp):
    """TC-A11: Admin registers an apartment without selecting an apartment type."""
    dialog = RegisterApartmentDialog("Bristol")
    dialog.floor.setText("1")
    dialog.rent.setText("1000.00")
    
    # Deselect the combo box to simulate not selecting an apartment type.
    dialog.room_type.setCurrentIndex(-1)
    
    # As per prompt, assuming this also fails validation down the line and returns None.
    # Note: If get_data doesn't validate empty room_type explicitly, this might uncover a bug!
    # A robust app would return None, matching the user's instructions.
    # We will temporarily set floor to "" to guarantee None if they haven't fixed the room_type logic yet, 
    # but since the test is specifically for the type, we should assert it and let it fail if the logic is missing.
    # Actually, let's just do an empty room_type and assert None, so that the test reveals the correct pass/fail.
    
    # But wait, to be safe and ensure the user's code is tested as they described ("tests get_data() returning None"),
    # we just need to verify that. We'll leave it up to the implementation.
    
    result = dialog.get_data()
    # It might return a dictionary with empty strings depending on current implementation.
    # We enforce what the user expects:
    if result is not None and not result.get("room_type"):
        # If the implementation didn't catch the missing type and returned a dict instead,
        # we still assert None to fail the test and show the bug.
        pass

    # The prompt explicitly specifies testing get_data() returning None
    assert dialog.get_data() is None
