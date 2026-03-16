"""Tests for user authentication — database/db_service.authenticate_user"""

from database.db_service import authenticate_user, create_user, deactivate_user


def test_valid_login_returns_user_dict():
    uid = create_user("testuser", "Pass@123", "finance", "Test", "User",
                       "test@pams.co.uk")
    result = authenticate_user("testuser", "Pass@123")
    assert result is not None
    assert result["user_id"] == uid
    assert result["role"] == "finance"
    assert result["username"] == "testuser"


def test_wrong_password_returns_none():
    create_user("testuser", "Pass@123", "admin", "Test", "User",
                "test@pams.co.uk")
    result = authenticate_user("testuser", "WrongPassword")
    assert result is None


def test_nonexistent_username_returns_none():
    result = authenticate_user("ghost_user", "anything")
    assert result is None


def test_deactivated_user_cannot_login():
    uid = create_user("deactuser", "Pass@123", "admin", "De", "Activated",
                       "deact@pams.co.uk")
    deactivate_user(uid)
    result = authenticate_user("deactuser", "Pass@123")
    assert result is None
