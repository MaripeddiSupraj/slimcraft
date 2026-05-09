from slimcraft.fixer import (
    fix_dockerfile,
    fix_apt_get,
    fix_pip,
    fix_apk,
    fix_yum,
    fix_user,
    fix_workdir,
)


class TestFixAptGet:
    def test_adds_y(self):
        content = "RUN apt-get install curl\n"
        fixed, n = fix_apt_get(content)
        assert n == 1
        assert fixed == "RUN apt-get install -y curl\n"

    def test_skips_when_y_present(self):
        content = "RUN apt-get install -y curl\n"
        fixed, n = fix_apt_get(content)
        assert n == 0
        assert fixed == content

    def test_skips_non_run_lines(self):
        content = "FROM ubuntu:22.04\nRUN apt-get install curl\n"
        fixed, n = fix_apt_get(content)
        assert n == 1
        assert "apt-get install -y" in fixed

    def test_multiple_occurrences(self):
        content = (
            "RUN apt-get install curl\n"
            "RUN apt-get install wget && apt-get install vim\n"
        )
        fixed, n = fix_apt_get(content)
        assert n == 3

    def test_apt_get_update(self):
        content = "RUN apt-get update\n"
        fixed, n = fix_apt_get(content)
        assert n == 0  # update, not install


class TestFixPip:
    def test_adds_no_cache_dir(self):
        content = "RUN pip install requests\n"
        fixed, n = fix_pip(content)
        assert n == 1
        assert fixed == "RUN pip install --no-cache-dir requests\n"

    def test_skips_when_no_cache_dir_present(self):
        content = "RUN pip install --no-cache-dir requests\n"
        fixed, n = fix_pip(content)
        assert n == 0

    def test_skips_non_run_lines(self):
        content = "RUN pip install requests\n"
        fixed, n = fix_pip(content)
        assert n == 1

    def test_multiple_pip_installs(self):
        content = (
            "RUN pip install requests && pip install flask\n"
        )
        fixed, n = fix_pip(content)
        assert n == 2
        assert "pip install --no-cache-dir requests" in fixed
        assert "pip install --no-cache-dir flask" in fixed


class TestFixApk:
    def test_adds_no_cache(self):
        content = "RUN apk add curl\n"
        fixed, n = fix_apk(content)
        assert n == 1
        assert fixed == "RUN apk add --no-cache curl\n"

    def test_skips_when_no_cache_present(self):
        content = "RUN apk add --no-cache curl\n"
        fixed, n = fix_apk(content)
        assert n == 0

    def test_skips_non_run_lines(self):
        content = "FROM alpine:3.18\n"
        fixed, n = fix_apk(content)
        assert n == 0


class TestFixYum:
    def test_adds_y_install(self):
        content = "RUN yum install curl\n"
        fixed, n = fix_yum(content)
        assert n == 1
        assert fixed == "RUN yum install -y curl\n"

    def test_adds_y_update(self):
        content = "RUN yum update\n"
        fixed, n = fix_yum(content)
        assert n == 1
        assert fixed == "RUN yum update -y\n"

    def test_skips_when_y_present(self):
        content = "RUN yum install -y curl\n"
        fixed, n = fix_yum(content)
        assert n == 0

    def test_dnf(self):
        content = "RUN dnf install curl\n"
        fixed, n = fix_yum(content)
        assert n == 1
        assert fixed == "RUN dnf install -y curl\n"

    def test_zypper(self):
        content = "RUN zypper install curl\n"
        fixed, n = fix_yum(content)
        assert n == 1
        assert fixed == "RUN zypper install -y curl\n"


class TestFixUser:
    def test_adds_user_nonroot(self):
        content = "FROM ubuntu:22.04\nCMD [\"bash\"]\n"
        fixed, n = fix_user(content)
        assert n == 1
        assert "USER nonroot" in fixed

    def test_skips_if_user_exists(self):
        content = "FROM ubuntu:22.04\nUSER appuser\nCMD [\"bash\"]\n"
        fixed, n = fix_user(content)
        assert n == 0
        assert fixed == content

    def test_inserts_before_cmd(self):
        content = "FROM ubuntu:22.04\nRUN apt-get update\nCMD [\"bash\"]\n"
        fixed, n = fix_user(content)
        lines = fixed.splitlines()
        cmd_idx = lines.index('CMD ["bash"]')
        user_idx = lines.index("USER nonroot")
        assert user_idx < cmd_idx

    def test_inserts_before_entrypoint(self):
        content = "FROM ubuntu:22.04\nENTRYPOINT [\"bash\"]\n"
        fixed, n = fix_user(content)
        lines = fixed.splitlines()
        ep_idx = lines.index('ENTRYPOINT ["bash"]')
        user_idx = lines.index("USER nonroot")
        assert user_idx < ep_idx

    def test_appends_if_no_cmd(self):
        content = "FROM ubuntu:22.04\nRUN apt-get update\n"
        fixed, n = fix_user(content)
        assert fixed.strip().endswith("USER nonroot")


class TestFixWorkdir:
    def test_adds_workdir(self):
        content = "FROM ubuntu:22.04\nRUN apt-get update\n"
        fixed, n = fix_workdir(content)
        assert n == 1
        assert "WORKDIR /app" in fixed

    def test_skips_if_workdir_exists(self):
        content = "FROM ubuntu:22.04\nWORKDIR /app\nRUN apt-get update\n"
        fixed, n = fix_workdir(content)
        assert n == 0

    def test_inserts_after_from(self):
        content = "FROM ubuntu:22.04\nRUN apt-get update\n"
        fixed, n = fix_workdir(content)
        lines = fixed.splitlines()
        from_idx = lines.index("FROM ubuntu:22.04")
        workdir_idx = lines.index("WORKDIR /app")
        assert workdir_idx == from_idx + 1


class TestFixDockerfile:
    def test_no_changes_needed(self):
        content = (
            "FROM ubuntu:22.04\n"
            "WORKDIR /app\n"
            "RUN apt-get update && apt-get install -y curl\n"
            "USER appuser\n"
            "CMD [\"bash\"]\n"
        )
        fixed, changes = fix_dockerfile(content)
        assert len(changes) == 0
        assert fixed == content

    def test_all_fixes_applied(self):
        content = (
            "FROM ubuntu:22.04\n"
            "RUN apt-get install curl\n"
            "RUN pip install requests\n"
            "RUN apk add curl\n"
            "CMD [\"bash\"]\n"
        )
        fixed, changes = fix_dockerfile(content)
        assert "apt-get install -y" in fixed
        assert "pip install --no-cache-dir" in fixed
        assert "apk add --no-cache" in fixed
        assert "USER nonroot" in fixed
        assert "WORKDIR /app" in fixed

    def test_changes_list(self):
        content = (
            "FROM ubuntu:22.04\n"
            "RUN apt-get install curl\n"
            "CMD [\"bash\"]\n"
        )
        fixed, changes = fix_dockerfile(content)
        ids = {c["id"] for c in changes}
        assert "apt-y" in ids
        assert "user" in ids
        assert "workdir" in ids

    def test_rationale_in_changes(self):
        content = (
            "FROM ubuntu:22.04\n"
            "RUN apt-get install curl\n"
            "CMD [\"bash\"]\n"
        )
        fixed, changes = fix_dockerfile(content)
        for c in changes:
            assert "description" in c
            assert c["count"] > 0
