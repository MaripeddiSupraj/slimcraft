# Homebrew Tap Instructions for slimcraft

1. Ensure your project builds a standalone CLI with an entry point in `pyproject.toml`:

    [project.scripts]
    slimcraft = "slimcraft.cli:main"

2. Publish a release on GitHub with a versioned tag (e.g., v0.1.0).

3. In your Homebrew tap repo, add a formula like:

    class Slimcraft < Formula
      include Language::Python::Virtualenv
      desc "Agentic container hardening CLI"
      homepage "https://github.com/MaripeddiSupraj/slimcraft"
      url "https://github.com/MaripeddiSupraj/slimcraft/archive/refs/tags/v0.1.0.tar.gz"
      sha256 "..."
      license "MIT"

      depends_on "python@3.11"

      def install
        virtualenv_install_with_resources
      end

      test do
        system "#{bin}/slimcraft", "--help"
      end
    end

4. Update the README with Homebrew install instructions after publishing.

5. Test with:

    brew tap MaripeddiSupraj/slimcraft
    brew install slimcraft
