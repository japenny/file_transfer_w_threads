import os, sys, re


class Archiver:
    """
    A class for archiving multiple files into a single archive file and extracting files from archives.
    Uses a custom binary format with headers containing file metadata.
    """

    def __init__(self):
        pass

    def archive(self, output_path, files):
        """
        Archives multiple files into a single file.

        Args:
            output_path (str): Path where the archive will be created
            files (list): List of file paths to archive

        Exits with error code 1 if any operation fails
        """
        try:
            # Open output file with write, create, and truncate flags
            out_fd = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)
        except Exception as e:
            os.write(2, f"Failed to open output file: {str(e)}\n".encode())
            sys.exit(1)

        for file in files:
            # Validate file exists
            if not os.path.isfile(file):
                os.write(2, f"File: {file}: does not exist!\n".encode())
                os.close(out_fd)
                sys.exit(1)

            try:
                fd = os.open(file, os.O_RDONLY)

                # Create header information:
                # - 8 bytes for file size
                # - 8 bytes for filename length
                # - Variable bytes for filename
                filename = os.path.basename(file).encode()
                filename_len = len(filename)
                filename_len = f"{filename_len:08d}".encode()
                file_stat = os.fstat(fd)
                filesize = file_stat.st_size
                filesize = f"{filesize:08d}".encode()

                # Write header to output file
                os.write(out_fd, filesize)
                os.write(out_fd, filename_len)
                os.write(out_fd, filename)

                # Write file contents in chunks
                while True:
                    chunk = os.read(fd, 4096)
                    if not chunk:
                        break
                    os.write(out_fd, chunk)

            except Exception as e:
                os.write(2, f"Error archiving {file}: {str(e)}\n".encode())
                os.close(out_fd)
                sys.exit(1)
            finally:
                os.close(fd)

    def extract(self, archive_path):
        """
        Extracts files from an archive.

        Args:
            archive_path (str): Path to the archive file

        Exits with error code 1 if extraction fails
        Note: Currently only extracts the first file in the archive
        """
        try:
            fd_in = os.open(archive_path, os.O_RDONLY)
        except Exception as e:
            os.write(2, f"Failed to open archive file: {str(e)}\n".encode())
            sys.exit(1)
        filesize = os.fstat(fd_in).st_size

        iters = 0
        # FIXME: Missing loop to extract multiple files from archive

        while True:
            # Read file size from header (8 bytes)
            filesize_byte = os.read(fd_in, 8)
            if not filesize_byte or len(filesize_byte) < 8:
                if iters == 0:
                    print(f"Error reading header byte size: Got {filesize_byte}")
                    sys.exit(1)
                else:
                    os.close(fd_in)
                    break
            iters += 1
            filesize = int(filesize_byte.decode())

            # Read filename length from header (8 bytes)
            filename_len_byte = os.read(fd_in, 8)
            if not filename_len_byte or len(filename_len_byte) < 8:
                print(f"Error reading header filename len: Got {filename_len_byte}")
                sys.exit(1)
            filename_len = int(filename_len_byte.decode())

            # Read filename (variable length based on filename_len)
            filename_byte = os.read(fd_in, filename_len)
            if not filename_byte or len(filename_byte) < 1:
                os.write(2, f"Error reading header filename: Got {filename_byte}".encode())
                os.close(fd_in)
                sys.exit(1)
            filename = filename_byte.decode()
            filename = 'new_' + filename  # Prepend 'new_' to avoid overwriting original

            try:
                # Open output file for writing
                fd_out = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o644)

                # Write file contents in chunks
                remaining = filesize
                while remaining > 0:
                    chunk_size = min(remaining, 4096)
                    chunk = os.read(fd_in, chunk_size)
                    if not chunk:
                        os.write(2, f"Error: Unexpected end of file while reading {filename}".encode())
                        os.close(fd_out)
                        os.close(fd_in)
                        sys.exit(1)

                    os.write(fd_out, chunk)
                    remaining -= len(chunk)

            except Exception as e:
                os.write(2, f"Error creating file {filename}: {e}\n".encode())
                if 'fd_out' in locals():
                    os.close(fd_out)
                os.close(fd_in)
                sys.exit(1)
            finally:
                if 'fd_out' in locals():
                    os.close(fd_out)


