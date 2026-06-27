import sqlite3, json

token = "eyJhY2Nlc3NfdG9rZW4iOiJleUowZVhBaU9pSnFkM1FpTENKaGJHY2lPaUpJVXpJMU5pSjkuZXlKcGMzTWlPaUoxYlhNaUxDSnpkV0lpT2pJM05UZ3dOakF4TWpFc0ltRjFaQ0k2SW1kaGIyUnBibWQ0SWl3aVpYaHdJam94TnpneU1EY3pOREEwTENKMVkybGtJam9pT1RFek5qazJNelUyTlRrNU1qQTBPVFk0TUNJc0ltcDBhU0k2SWpGeU5qRjZlVzF1Y0hjaUxDSm9ZbDlwWkNJNklqZ3dOVEkzTVRVeU1TSjkudDVaVTFNTnZTaXR6bVB4ZndlMUNTXzB1UFlBRU9NbTRyRGMxQUdpZE4wUSIsImFjY2Vzc190b2tlbl9leHBpcmVzX2F0IjoiMjAyNi0wNi0yMVQyMDoyMzoyNC4wMDBaIiwiYWNjZXNzX3Rva2VuX2xpZmVfdGltZSI6Mjg4MDAsInJlZnJlc2hfdG9rZW4iOiIiLCJyZWZyZXNoX3Rva2VuX2V4cGlyZXNfYXQiOiIyMDI2LTA3LTA2VDEyOjIzOjI0LjE2OVoiLCJyZWZyZXNoX3Rva2VuX2xpZmVfdGltZSI6MTI5NjAwMCwibWVyZ2VkIjp0cnVlLCJ0aW1lc3RhbXAiOjE3ODIwNDQ2MDM5ODV9"

db = sqlite3.connect("E:/视频生成/dreamina-auto-register-main/backend/insmind.db")
c = db.cursor()
c.execute("INSERT OR IGNORE INTO insmind_accounts (email, token, user_id, credits, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, datetime(), datetime())",
    ("jppdk5rqfz@ruutukf.com", token, "2758060121", 0, "active"))
db.commit()
for row in c.execute("SELECT email, credits, status FROM insmind_accounts"):
    print(row)
db.close()
