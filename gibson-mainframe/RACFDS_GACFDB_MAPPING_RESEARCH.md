# GACF.DB to RACFDS Mapping

Existing password hashes cannot be converted into legacy RACF DES hashes because password hashes are one-way. Gibson now materialises protected/KDFAES-style records for existing unknown-password users and generates crackable legacy-DES records only for seeded vulnerable lab identities or password events where plaintext is available at set/change time.
