"""CV generator that adapts each résumé to the job application."""

from cv_generator.native_libs import prepare_native_libraries

# Must happen before any weasyprint import in the process.
prepare_native_libraries()
