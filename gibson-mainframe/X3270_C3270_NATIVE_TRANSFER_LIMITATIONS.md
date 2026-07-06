# x3270/c3270 native Transfer limitations

Native x3270/c3270 `Transfer()` requires the emulator to be connected in true 3270 mode and requires host-side IND$FILE protocol behavior. This package does not claim full structured-field Transfer compatibility. Use command-mode IND$FILE or s3270 scripted command-mode validation until full TN3270 client validation is completed.
