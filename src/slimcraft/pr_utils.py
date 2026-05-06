def open_pr_with_diff(original_path, rewritten_content, rationale):
    """
    Stub for PR creation logic. Prints what would be done.
    """
    print("[STUB] Would open a PR with the following diff and rationale:")
    print("--- ORIGINAL ---")
    with open(original_path, 'r') as f:
        print(f.read())
    print("--- REWRITTEN ---")
    print(rewritten_content)
    print("--- RATIONALE ---")
    print(rationale)
