import re

from sandbox.daml_sandbox import DamlSandbox


def _render_template_skeleton(name: str, fields: list[dict]) -> str:
    field_lines = "\n".join(
        f"    {f['name']} : {f['type']}" for f in fields
    )
    return (
        f"module {name} where\n\n"
        f"template {name}\n"
        f"  with\n"
        f"{field_lines}\n"
        f"  where\n"
    )


async def create_template(
    sandbox: DamlSandbox,
    name: str,
    fields: list[dict],
) -> str:
    content = _render_template_skeleton(name, fields)
    file_path = f"daml/{name}.daml"
    await sandbox.files.write(file_path, content)
    return f"Created template {name} at {file_path}"


async def add_signatory(
    sandbox: DamlSandbox,
    template_name: str,
    party_field: str,
) -> str:
    file_path = f"daml/{template_name}.daml"
    code = await sandbox.files.read(file_path)

    where_pattern = re.compile(r"(  where\n)")

    if not where_pattern.search(code):
        return f"ERROR: could not locate 'where' block in {file_path}"

    replacement = f"  where\n    signatory {party_field}\n"
    new_code = where_pattern.sub(replacement, code, count=1)

    await sandbox.files.write(file_path, new_code)
    return f"Added signatory {party_field} to {template_name}"


async def add_observer(
    sandbox: DamlSandbox,
    template_name: str,
    party_field: str,
) -> str:
    file_path = f"daml/{template_name}.daml"
    code = await sandbox.files.read(file_path)

    signatory_pattern = re.compile(r"(    signatory [^\n]+\n)")

    if signatory_pattern.search(code):
        new_code = signatory_pattern.sub(
            f"\\1    observer {party_field}\n",
            code,
            count=1,
        )
    else:
        where_pattern = re.compile(r"(  where\n)")
        if not where_pattern.search(code):
            return f"ERROR: could not locate 'where' block in {file_path}"
        new_code = where_pattern.sub(
            f"  where\n    observer {party_field}\n",
            code,
            count=1,
        )

    await sandbox.files.write(file_path, new_code)
    return f"Added observer {party_field} to {template_name}"


async def add_choice(
    sandbox: DamlSandbox,
    template_name: str,
    choice_name: str,
    controller: str,
    params: list[dict],
    return_type: str,
    body: str,
) -> str:
    file_path = f"daml/{template_name}.daml"
    code = await sandbox.files.read(file_path)

    if params:
        param_lines = "\n".join(
            f"    {p['name']} : {p['type']}" for p in params
        )
        params_block = f"  with\n{param_lines}\n"
    else:
        params_block = ""

    choice_block = (
        f"\n    choice {choice_name} : {return_type}\n"
        f"{params_block}"
        f"      controller {controller}\n"
        f"      do\n"
        f"        {body}\n"
    )

    new_code = code.rstrip() + "\n" + choice_block
    await sandbox.files.write(file_path, new_code)
    return f"Added choice {choice_name} to {template_name}"


async def add_ensure(
    sandbox: DamlSandbox,
    template_name: str,
    condition: str,
) -> str:
    file_path = f"daml/{template_name}.daml"
    code = await sandbox.files.read(file_path)

    existing = re.search(r"(    ensure )(.+)", code)
    if existing:
        old_ensure = existing.group(0)
        new_ensure = f"    ensure {existing.group(2).strip()} && {condition}"
        new_code = code.replace(old_ensure, new_ensure, 1)
    else:
        signatory_pattern = re.compile(r"(    signatory [^\n]+\n)")
        if signatory_pattern.search(code):
            new_code = signatory_pattern.sub(
                f"\\1    ensure {condition}\n",
                code,
                count=1,
            )
        else:
            where_pattern = re.compile(r"(  where\n)")
            new_code = where_pattern.sub(
                f"  where\n    ensure {condition}\n",
                code,
                count=1,
            )

    await sandbox.files.write(file_path, new_code)
    return f"Added ensure clause to {template_name}: {condition}"


async def read_template(
    sandbox: DamlSandbox,
    template_name: str,
) -> str:
    file_path = f"daml/{template_name}.daml"
    return await sandbox.files.read(file_path)


async def write_full_template(
    sandbox: DamlSandbox,
    template_name: str,
    content: str,
) -> str:
    file_path = f"daml/{template_name}.daml"
    await sandbox.files.write(file_path, content)
    return f"Wrote {file_path}"
