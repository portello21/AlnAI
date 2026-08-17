from cryptography.fernet import Fernet

from core.encrypted_backup import decrypt_backup, encrypt_backup


def test_backup_round_trip_is_encrypted():
    key = Fernet.generate_key().decode("ascii")
    source = {"format": "rog-ai-backup-v1", "tables": {"memories_v2": [{"content": "privado"}]}}
    encrypted = encrypt_backup(source, key)
    assert b"privado" not in encrypted
    assert decrypt_backup(encrypted, key) == source


def test_backup_rejects_wrong_key_or_format():
    key = Fernet.generate_key().decode("ascii")
    payload = encrypt_backup({"format": "wrong", "tables": {}}, key)
    try:
        decrypt_backup(payload, key)
    except ValueError as exc:
        assert "unsupported" in str(exc)
    else:
        raise AssertionError("invalid format accepted")
