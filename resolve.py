# if not found packages, show files, cc -> gcc, java -> ?
import subprocess
from io import BytesIO


def parse_dockerfile_stream(stream, num_lines=None, fix=False):
    stream.seek(0)
    lines = []
    catline = []
    for i, line in enumerate(stream):
        lrstrip = line.rstrip()
        # Handle Dockerfile's RUN multiline support
        if lrstrip and lrstrip[-1] == '\\':
            if not catline:
                if line.lstrip().split(' ', 1)[0].lower() == 'run':
                    catline.append(line)
            else:
                catline.append(line)
        else:
            if catline:
                catline.append(line)
                lines.append(''.join(catline))
                catline = []
            else:
                lines.append(line)
        if num_lines and len(lines) == num_lines:
            break
    else:
        return None
    if fix:
        line = lines[-1]
        lines = lines[:-1]
        # TODO handle SHELL FORM
        # TODO allow custom shell
        l1 = 'RUN apt-get update && apt-get install -y strace && mkdir /tmp/strace_output\n'
        l2= 'ENTRYPOINT ["strace", "-I4", "-e", "file", "-ff", "-o", "/tmp/strace_output/strace_output", "/bin/sh", "-c", "' + line.lstrip().split(' ', 1)[1].rstrip().replace(r'"', r'\"').replace('\t', r'\t') + '"]\n'
        line = ''.join([l1, l2])
        lines.append(line)
    return BytesIO('\n'.join(lines))


def build_with(stream, image_tag):
    p_out = subprocess.Popen('docker build -t %s -' % image_tag, shell=True, stdin=subprocess.PIPE)
    p_out.stdin.write(stream.read())
    p_out.stdin.close()
    p_out.wait()
    return p_out


def docker_get_strace_output(docker_image_id):
    # TODO check return value error
    # TODO handle finally cleanup
    p_out = subprocess.Popen('docker create -it --cap-add=SYS_PTRACE --pid=host %s' % docker_image_id, shell=True, stdout=subprocess.PIPE)
    docker_container_id = p_out.stdout.read().rstrip()
    p_out.stdout.close()
    p_out.wait()
    p_out = subprocess.Popen('docker start -ia %s' % docker_container_id, shell=True)
    p_out.wait()
    # TODO handle processing only strace output files
    p_out = subprocess.Popen('docker cp %s:/tmp/strace_output - | tar -xvO' % docker_container_id, shell=True, stdout=subprocess.PIPE)
    strace_output = p_out.stdout.read()
    p_out.stdout.close()
    p_out.wait()
    p_out = subprocess.Popen('docker rm -f %s' % docker_container_id, shell=True)
    p_out.wait()
    return strace_output


def docker_get_aptsources_output(docker_image_id):
    # TODO check re value error
    # TODO make this better
    p_out = subprocess.Popen('docker run -it --rm --entrypoint /bin/cat %s /etc/apt/sources.list' % docker_image_id, shell=True, stdout=subprocess.PIPE)
    debfiles = p_out.stdout.read()
    p_out.stdout.close()
    p_out.wait()
    return debfiles


def parse_strace_output(strace_output):
    fnames = []
    for line in strace_output.split('\n'):
        #print(line)
        if '=' not in line:
            continue
        data = line.rsplit(' = ', 1)
        if len(data) >= 2 and 'ENOENT' in data[1]:
            # TODO make this less flaky
            fname = data[0].split('"', 1)[1].split('", ', 1)[0]
#            fname = data[0].split('"', 1)[1].rsplit('"', 1)[0]
            if fname.startswith('/usr/local') or fname[0] != '/' or fname.startswith('/tmp'):
                continue
            fnames.append(fname)
    return fnames


def build_till_next_error(stream, image_tag):
    i = 1
    while True:
        s = parse_dockerfile_stream(stream, i)
        if s is None:
            return None
        p_out = build_with(s, image_tag)
        if p_out.returncode != 0:
            p_out = build_with(parse_dockerfile_stream(stream, i, True), image_tag)
            return docker_get_strace_output(image_tag)
            break
        i += 1


def find_next_packages(input_stream, image_name):
    input_context = open('Dockerfile', 'rt')
    strace_output = build_till_next_error(input_context, 'build_tmp')
    if strace_output is None:
        print('build finished without errors')
        return
    #print(strace_output)
    missing_files = parse_strace_output(strace_output)
    #print(missing_files)
    #print(set(missing_files))
    sources = docker_get_aptsources_output('build_tmp')
    #print(sources)
    import aptfile
    import io
    s = io.BytesIO(sources)
    output = io.BytesIO()
    aptfile.update(s, output)
    output.seek(0)
    missing_packages = aptfile.find_packages(missing_files, output)
    print(missing_packages)


if __name__ == "__main__":
    find_next_packages('a', 'b')
