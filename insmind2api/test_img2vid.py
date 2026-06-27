"""Test img2vid with larger image"""
import subprocess, json, sys, time

# Upload
result = subprocess.run(
    ["curl", "-s", "-X", "POST", 
     "http://127.0.0.1:5105/api/v1/media/upload",
     "-H", "Content-Type: application/json",
     "-d", '{"image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAMAAAADACAIAAADdvvtQAAAEVklEQVR4nO3ca25VMQxF4eOrO2gGxnAYyw0SSAiqqrRnJ/G2s77fPFpn4aSgEt++/7iAux63fyZAQFCxgSAhIEgICBICgoSAICEgSAgIEgKChIAgISBICAgSAoKEgCAhIEie18HG6/8/Jq5rfOKXilP/JJ4V0GeKmfIrxzE99Q9oXTSf/E17x9Q2oJRuPv5IWpbULSCfbg4pqUlAzt30Lql8QLXSefeDL51R4YBKp9Mmo5IBtUmnQUbFAhq//1Ivrq7Gr08w6nyCz2LpnGHUyahAQEelUy4j9yv32HqqTMB3A5kPbqdhvIpMNxD1VJmJY0Cek3Iw/CbjdYUZDsjNMLvOjDYQ9VSclUtAPhOpYnhMzCIgk1mUMwzmlvwGchhBaSP7SZS5gainwSTTAqKeHvPMCYh62kw1ISDq6TTb3QFRT7MJW3wZj7q2BsT66TfnfQFRz07bpr0pIOrZb8/MdwREPVk2TJ5HNLwDYv3kWj3/tQFRj4Olp7AwIOrxse4seAPBMiDWj5tFJ7IkIOrxtOJcuMJgFhDrx9n002EDwSkg1o+/uWfEBoJNQC++R6eIiSfFBoJHQKyfWmadFxsIBgGxfiqacmpsIGQHxPqpSz87NhAkBITUgLi/qhNPkA0ECQEhLyDurx6Uc2QDQUJASAqI+6uT26fJBoKEgCAhIGQExAOon9etZxAbCBICgoSAICEgbA+IF3RXr6+/o9lAkBAQJAQECQFBQkCQEBAkBAQJAUFCQJAQECQEBMnzzk8K7ffE6QHxn2k2Fl/74VxhkBAQJAQECQFBQkCQEBAkBAQJAUFCQJAQECQEhO0BPfjH1KYeXz9ZNhAkBAQJAUFCQMgIiHd0P49bXxuxgSAhIEgICEkB8Qzq5PZpsoEgISDkBcQt1oNyjmwgSAgIqQFxi1UnniAbCBICQnZA3GJ16WfHBoJBQCyhiqacGhsIHgGxhGqZdV5sINgExBKqYuJJsYHgFFDwTav25p4RGwhmAbGEnE0/HTYQ/AJiCXlacS6rNhANuVl0IlxhcA2IJeRj3Vms3UA05GDpKSy/wmgo1+r58waCfUAsoSwbJr9pA9HQfntmvu8Ko6Gdtk176xuIhvrNmUc0SgXEEmo24YQNREOdZptzhdFQm6mmvYFoqMc8Mx/RNNRgks/L4DMfI/ejKCyyv4vB4sv49CkUFQZzswjIZBa1hMfEXALymUgJYTOr5DfQGzyJCqVjt4FsZ+Qj/CbjGJDnpNKF5Uy8rrC/cZ2Zp2O9gUrMbg/zCfhuoD+OXUXhnU6ZgA7MKCqkUyygfzJ6XV2F+5uieEB/T7lZRlEtncIBNcsoaqZTPqAGGUXldJoE9OYkSpQU9bvpFlCJkqJRN20DMiwpOnbTP6B3z29bTNE6mrMC+uBcJ/YUxxRzdED3Tr3OXwsnOPUPDiYhIEgICBICgoSAICEgSAgIEgKChIAgISBICAgSAoKEgCAhIEgICJfiJwbE184dxfwtAAAAAElFTkSuQmCC"}'],
    capture_output=True, text=True, timeout=30
)
print(f"UPLOAD: {result.stdout}")
try:
    upload = json.loads(result.stdout.strip())
    cdn = upload.get("cdn_url", "")
    print(f"CDN: {cdn}")
except: 
    print(f"PARSE FAIL: {result.stdout[:200]}")
    sys.exit(1)
