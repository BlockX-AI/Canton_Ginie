"""
Propose-Accept pattern injector.

Takes a compiled core DAML template and mechanically produces a matching
Proposal template alongside it.  The core template generation stays clean
and single-purpose; the proposal is a deterministic transformation.

The canonical Canton Propose-Accept pattern:
  - ProposalTemplate: signatory = initiator, observer = acceptor(s)
  - Accept choice:    creates the core template (both become signatories)
  - Reject choice:    archives the proposal
  - Cancel choice:    initiator can withdraw the proposal
"""

import re
import structlog

logger = structlog.get_logger()


def inject_proposal_pattern(
    core_code: str,
    initiator: str,
    acceptors: list[str],
) -> str:
    """Take a compiled core template and generate the proposal template alongside it.

    Returns a new DAML source that contains:
      1. The original core template (unchanged)
      2. A {TemplateName}Proposal template with Accept/Reject/Cancel choices

    The proposal embeds all core fields in its ``with`` block so the acceptor
    can inspect the full terms before accepting.
    """
    template_name = _extract_template_name(core_code)
    if not template_name:
        logger.warning("Could not extract template name from core code, skipping proposal injection")
        return core_code

    fields = _extract_fields(core_code)
    if not fields:
        logger.warning("Could not extract fields from core code, skipping proposal injection")
        return core_code

    if "proposal" in core_code.lower():
        return core_code

    # Build the proposal template
    proposal_name = f"{template_name}Proposal"

    # Build field block (same fields as core template)
    field_lines = "\n".join(f"    {f['name']} : {f['type']}" for f in fields)

    # Build the core template creation payload (all fields forwarded)
    create_fields = "\n".join(f"        {f['name']} = {f['name']}" for f in fields)

    # Determine party roles
    # The initiator is the sole signatory of the proposal
    # Acceptors are observers who can exercise Accept
    acceptor_list = ", ".join(acceptors) if acceptors else "acceptor"

    # Build the proposal template code
    proposal_code = f"""
template {proposal_name}
  with
{field_lines}
  where
    signatory {initiator}
    observer {acceptor_list}

    choice {proposal_name}_Accept : ContractId {template_name}
      controller {acceptors[0] if acceptors else 'acceptor'}
      do
        create {template_name} with
{create_fields}

    choice {proposal_name}_Reject : ()
      controller {acceptors[0] if acceptors else 'acceptor'}
      do
        return ()

    choice {proposal_name}_Cancel : ()
      controller {initiator}
      do
        return ()
"""

    # Append proposal template after the core template
    combined = core_code.rstrip() + "\n\n" + proposal_code.strip() + "\n"

    logger.info("Proposal pattern injected",
                core_template=template_name,
                proposal_template=proposal_name,
                initiator=initiator,
                acceptors=acceptors)

    return combined


def _extract_template_name(code: str) -> str | None:
    match = re.search(r"^template\s+(\w+)", code, re.MULTILINE)
    return match.group(1) if match else None


def _extract_module_name(code: str) -> str | None:
    match = re.search(r"^module\s+(\S+)\s+where", code, re.MULTILINE)
    return match.group(1) if match else None


def _extract_fields(code: str) -> list[dict]:
    """Extract fields from the first template's ``with`` block."""
    match = re.search(
        r"template\s+\w+\s+with\s+(.*?)\s+where",
        code,
        re.DOTALL,
    )
    if not match:
        return []

    fields = []
    for line in match.group(1).split("\n"):
        line = line.strip()
        if ":" in line and not line.startswith("--"):
            name, ftype = line.split(":", 1)
            name = name.strip()
            ftype = ftype.strip()
            if name and ftype:
                fields.append({"name": name, "type": ftype})
    return fields
