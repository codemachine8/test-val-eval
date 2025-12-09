"""
Order-Dependent Flaky Tests - Easy Difficulty

These tests fail when run in certain orders because they share state
through the Database singleton and don't properly clean up.

Root Cause: Tests modify shared state (Database._data) without isolation.
Expected Fix: Add proper setup/teardown or use fixtures to isolate tests.

Failure Rate: ~30% when run in random order
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from database import Database, UserService


class TestUserCreation:
    """Tests for user creation - these pollute shared state."""
    
    def test_create_single_user(self):
        """Create a single user and verify."""
        db = Database()
        db.connect()
        
        service = UserService(db)
        user_id = service.create_user("Alice", "alice@example.com")
        
        assert user_id > 0
        user = service.get_user(user_id)
        assert user["name"] == "Alice"
        assert user["email"] == "alice@example.com"
        # Bug: No cleanup - leaves data in Database._data
    
    def test_create_multiple_users(self):
        """Create multiple users."""
        db = Database()
        db.connect()
        
        service = UserService(db)
        id1 = service.create_user("Bob", "bob@example.com")
        id2 = service.create_user("Charlie", "charlie@example.com")
        
        assert id1 != id2
        assert service.get_user(id1)["name"] == "Bob"
        assert service.get_user(id2)["name"] == "Charlie"
        # Bug: No cleanup


class TestUserCount:
    """Tests that depend on database being in a specific state."""
    
    def test_empty_database_has_no_users(self):
        """
        FLAKY: This test assumes the database is empty.
        Fails if test_create_single_user or test_create_multiple_users runs first.
        """
        db = Database()
        db.connect()
        
        service = UserService(db)
        users = db.get_all("users")
        
        # This assertion will fail if other tests have run first
        assert len(users) == 0, f"Expected empty database, found {len(users)} users"
    
    def test_count_after_adding_one_user(self):
        """
        FLAKY: Assumes starting from empty state.
        """
        db = Database()
        db.connect()
        
        service = UserService(db)
        initial_count = len(db.get_all("users"))
        
        service.create_user("David", "david@example.com")
        
        final_count = len(db.get_all("users"))
        # This will fail if initial_count wasn't 0
        assert final_count == 1, f"Expected 1 user, found {final_count}"


class TestTransactionCount:
    """Tests that check transaction count - very order-dependent."""
    
    def test_transaction_count_starts_at_zero(self):
        """
        FLAKY: Transaction count persists across tests.
        """
        db = Database()
        
        # This will fail if any other test has done database operations
        assert db.get_transaction_count() == 0, \
            f"Expected 0 transactions, found {db.get_transaction_count()}"
    
    def test_transaction_count_increments(self):
        """
        FLAKY: Depends on starting transaction count.
        """
        db = Database()
        db.connect()
        
        initial = db.get_transaction_count()
        db.insert("test_table", {"key": "value"})
        
        # This assertion is actually correct, but the test name implies
        # it should start at 0
        assert db.get_transaction_count() == initial + 1


class TestDatabaseConnection:
    """Tests for database connection state."""
    
    def test_initially_disconnected(self):
        """
        FLAKY: Connection state persists via singleton.
        """
        db = Database()
        
        # This fails if another test left the connection open
        assert not db.is_connected(), "Database should be disconnected initially"
    
    def test_connect_and_disconnect(self):
        """Test connection lifecycle."""
        db = Database()
        
        db.connect()
        assert db.is_connected()
        
        db.disconnect()
        assert not db.is_connected()
    
    def test_operations_require_connection(self):
        """Test that operations fail when disconnected."""
        db = Database()
        # Bug: Doesn't ensure disconnected state first
        
        with pytest.raises(ConnectionError):
            db.insert("table", {"key": "value"})


class TestUserDeactivation:
    """Tests for user deactivation - exposes caching bugs."""
    
    def test_deactivate_user(self):
        """
        Test user deactivation.
        Note: This test exposes a bug in UserService.deactivate_user
        where the database isn't actually updated.
        """
        db = Database()
        db.connect()
        
        service = UserService(db)
        user_id = service.create_user("Eve", "eve@example.com")
        
        # Deactivate
        result = service.deactivate_user(user_id)
        assert result is True
        
        # Get fresh from DB (not cache)
        db_user = db.get("users", user_id)
        # This may fail due to the bug in deactivate_user
        assert db_user["active"] is False, "User should be deactivated in database"
    
    def test_count_active_users(self):
        """
        FLAKY: Depends on how many users exist and their states.
        """
        db = Database()
        db.connect()
        
        service = UserService(db)
        
        # Create some users
        service.create_user("Frank", "frank@example.com")
        service.create_user("Grace", "grace@example.com")
        
        active_count = service.count_active_users()
        
        # This assertion is fragile - depends on test order
        assert active_count >= 2, f"Expected at least 2 active users, found {active_count}"
