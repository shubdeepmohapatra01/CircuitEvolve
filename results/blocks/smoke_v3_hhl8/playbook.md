# Playbook (open naming)

## candidate (3)

- **R1** Phase-polynomial view: between H gates every rz acts on a parity (XOR) of wires, tracked through the CNOTs; rz gates on the same parity merge into one rz(sum), and an rz on a parity that is later recreated can be moved there.  
  _shown 0, pass 0/0 with vs 0/0 without, improvements 0_ 
- **R2** If angles coincide numerically in every instance (e.g. a0 == a1), an exact rewrite in a_i cannot use that (it is checked on random angles); write a template with free parameters p_j instead, which is fitted per instance.  
  _shown 0, pass 0/0 with vs 0/0 without, improvements 0_ 
- **R3** A 2-qubit unitary needs at most 3 cx; with p_j parameters a template 'Euler(q0) Euler(q1) cx rz rz cx ...' can replace a 2-qubit stretch that currently holds more rotations than the template.  
  _shown 0, pass 0/0 with vs 0/0 without, improvements 0_ 
