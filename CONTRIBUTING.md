# Contributing to Clippy Vision

Thanks for your interest in contributing! Clippy Vision is an open-source project that welcomes contributions from the community.

## Ways to Contribute

- **Bug Reports**: Found a bug? Open an issue with details on how to reproduce it
- **Feature Requests**: Have an idea? Open an issue describing the feature and use case
- **Code Contributions**: Want to implement a feature or fix a bug? Submit a pull request
- **Documentation**: Help improve the docs, guides, or code comments
- **Testing**: Test the software on different systems and report issues

## Development Setup

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/clippy-vision.git`
3. Run setup: `.\setup.ps1`
4. Create a branch: `git checkout -b feature/your-feature-name`

## Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions focused and single-purpose
- Comment complex logic, but prefer self-documenting code

## Testing

Before submitting a PR:

1. Run the installation test: `python test_installation.py`
2. Test your changes with real usage
3. Ensure no new linter errors are introduced
4. Test on a clean database if modifying storage/schema

## Pull Request Process

1. Update the README.md or QUICKSTART.md if needed
2. Update requirements.txt if you added dependencies
3. Write a clear PR description explaining:
   - What problem does this solve?
   - What changes were made?
   - How was it tested?
4. Link any related issues
5. Be responsive to code review feedback

## Areas That Need Help

### High Priority
- [ ] Linux/Mac support (currently Windows-only)
- [ ] Electron GUI for easier user interaction
- [ ] Automated tests for classification pipeline
- [ ] Performance optimization for vision processing
- [ ] Better error handling and logging

### Medium Priority
- [ ] Docker/containerization support
- [ ] Alternative model support (LLaMA, Mistral, etc.)
- [ ] Web UI for database exploration
- [ ] Export/import conversation history
- [ ] Configurable retention policies

### Low Priority
- [ ] Plugin system for custom tools
- [ ] Integration with other productivity apps
- [ ] Alternative database backends
- [ ] Cloud sync option (with E2E encryption)

## Questions?

Open an issue or discussion on GitHub. I try to respond within 24-48 hours.

## Code of Conduct

- Be respectful and constructive
- Focus on the technical merit of ideas
- Welcome newcomers and help them learn
- Assume good intent

Happy coding! 🚀
