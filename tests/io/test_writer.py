import os
import tempfile

import numpy as np
import pandas as pd

from snps import SNPs
from snps.resources import ReferenceSequence, Resources
from snps.utils import gzip_file
from tests import BaseSNPsTestCase


class TestWriter(BaseSNPsTestCase):
    def run_writer_test(
        self, func_str, filename="", output_file="", expected_output="", **kwargs
    ):
        if func_str == "to_vcf":
            with tempfile.TemporaryDirectory() as tmpdir1:
                s = SNPs("tests/input/testvcf.vcf", output_dir=tmpdir1)

                r = Resources()
                r._reference_sequences["GRCh37"] = {}

                output = os.path.join(tmpdir1, output_file)
                with tempfile.TemporaryDirectory() as tmpdir2:
                    dest = os.path.join(tmpdir2, "generic.fa.gz")
                    gzip_file("tests/input/generic.fa", dest)

                    seq = ReferenceSequence(ID="1", path=dest)

                    r._reference_sequences["GRCh37"]["1"] = seq

                    if not filename:
                        result = s.to_vcf(**kwargs)
                    else:
                        result = s.to_vcf(filename, **kwargs)

                    self.assertEqual(result, output)

                    if expected_output:
                        # read result
                        with open(output, "r") as f:
                            actual = f.read()

                        # read expected result
                        with open(expected_output, "r") as f:
                            expected = f.read()

                        self.assertIn(expected, actual)

                self.run_parsing_tests_vcf(output)
        else:
            with tempfile.TemporaryDirectory() as tmpdir:
                snps = SNPs("tests/input/generic.csv", output_dir=tmpdir)
                dest = os.path.join(tmpdir, output_file)
                # https://stackoverflow.com/a/3071
                if not filename:
                    self.assertEqual(getattr(snps, func_str)(), dest)
                else:
                    self.assertEqual(getattr(snps, func_str)(filename), dest)
                self.run_parsing_tests(dest, "generic")

    def test_to_csv(self):
        self.run_writer_test("to_csv", output_file="generic_GRCh37.csv")

    def test_to_csv_filename(self):
        self.run_writer_test(
            "to_csv", filename="generic.csv", output_file="generic.csv"
        )

    def test_to_tsv(self):
        self.run_writer_test("to_tsv", output_file="generic_GRCh37.txt")

    def test_to_tsv_filename(self):
        self.run_writer_test(
            "to_tsv", filename="generic.txt", output_file="generic.txt"
        )

    def test_to_vcf(self):
        self.run_writer_test(
            "to_vcf",
            output_file="vcf_GRCh37.vcf",
            expected_output="tests/output/vcf_generic.vcf",
        )

    def test_to_vcf_filename(self):
        self.run_writer_test("to_vcf", filename="vcf.vcf", output_file="vcf.vcf")

    def test_to_vcf_chrom_prefix(self):
        self.run_writer_test(
            "to_vcf",
            output_file="vcf_GRCh37.vcf",
            expected_output="tests/output/vcf_chrom_prefix_chr.vcf",
            chrom_prefix="chr",
        )

    def test_save_snps_false_positive_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snps = SNPs("tests/input/generic.csv", output_dir=tmpdir)
            output = os.path.join(tmpdir, "generic_GRCh37.txt")
            self.assertEqual(snps.to_tsv(), output)

            s = ""
            with open(output, "r") as f:
                for line in f.readlines():
                    if "snps v" in line:
                        s += "# Generated by snps v1.2.3.post85.dev0+gb386302, https://pypi.org/project/snps/\n"
                    else:
                        s += line

            with open(output, "w") as f:
                f.write(s)

            self.run_parsing_tests(output, "generic")

    def test_save_snps_vcf_false_positive_build(self):
        with tempfile.TemporaryDirectory() as tmpdir1:
            snps = SNPs("tests/input/testvcf.vcf", output_dir=tmpdir1)

            r = Resources()
            r._reference_sequences["GRCh37"] = {}

            output = os.path.join(tmpdir1, "vcf_GRCh37.vcf")
            with tempfile.TemporaryDirectory() as tmpdir2:
                dest = os.path.join(tmpdir2, "generic.fa.gz")
                gzip_file("tests/input/generic.fa", dest)

                seq = ReferenceSequence(ID="1", path=dest)

                r._reference_sequences["GRCh37"]["1"] = seq

                self.assertEqual(snps.to_vcf(), output)

                s = ""
                with open(output, "r") as f:
                    for line in f.readlines():
                        if "snps v" in line:
                            s += '##source="vcf; snps v1.2.3.post85.dev0+gb386302; https://pypi.org/project/snps/"\n'
                        else:
                            s += line

                with open(output, "w") as f:
                    f.write(s)

            self.run_parsing_tests_vcf(output)

    def test_save_snps_vcf_discrepant_pos(self):
        with tempfile.TemporaryDirectory() as tmpdir1:
            s = SNPs("tests/input/testvcf.vcf", output_dir=tmpdir1)

            r = Resources()
            r._reference_sequences["GRCh37"] = {}

            output = os.path.join(tmpdir1, "vcf_GRCh37.vcf")
            with tempfile.TemporaryDirectory() as tmpdir2:
                dest = os.path.join(tmpdir2, "generic.fa.gz")
                gzip_file("tests/input/generic.fa", dest)

                seq = ReferenceSequence(ID="1", path=dest)

                r._reference_sequences["GRCh37"]["1"] = seq

                # create discrepant SNPs by setting positions outside reference sequence
                s._snps.loc["rs1", "pos"] = 0
                s._snps.loc["rs17", "pos"] = 118

                # esnure this is the right type after manual tweaking
                s._snps = s._snps.astype({"pos": np.uint32})

                self.assertEqual(s.to_vcf(), output)

            pd.testing.assert_frame_equal(
                s.discrepant_vcf_position,
                self.create_snp_df(
                    rsid=["rs1", "rs17"],
                    chrom=["1", "1"],
                    pos=[0, 118],
                    genotype=["AA", np.nan],
                ),
                check_exact=True,
            )

            expected = self.generic_snps_vcf().drop(["rs1", "rs17"])
            self.run_parsing_tests_vcf(output, snps_df=expected)

    def test_save_snps_vcf_phased(self):
        with tempfile.TemporaryDirectory() as tmpdir1:
            # read phased data
            s = SNPs("tests/input/testvcf_phased.vcf", output_dir=tmpdir1)

            # setup resource to use test FASTA reference sequence
            r = Resources()
            r._reference_sequences["GRCh37"] = {}

            output = os.path.join(tmpdir1, "vcf_GRCh37.vcf")
            with tempfile.TemporaryDirectory() as tmpdir2:
                dest = os.path.join(tmpdir2, "generic.fa.gz")
                gzip_file("tests/input/generic.fa", dest)

                seq = ReferenceSequence(ID="1", path=dest)

                r._reference_sequences["GRCh37"]["1"] = seq

                # save phased data to VCF
                self.assertEqual(s.to_vcf(), output)

            # read saved VCF
            self.run_parsing_tests_vcf(output, phased=True)

    def test_save_snps_phased(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # read phased data
            s = SNPs("tests/input/testvcf_phased.vcf", output_dir=tmpdir)
            dest = os.path.join(tmpdir, "vcf_GRCh37.txt")
            # save phased data to TSV
            self.assertEqual(s.to_tsv(), dest)
            # read saved TSV
            self.run_parsing_tests_vcf(dest, phased=True)

    def run_vcf_qc_test(
        self, expected_output, vcf_qc_only, vcf_qc_filter, cluster="c1"
    ):
        def f():
            with tempfile.TemporaryDirectory() as tmpdir1:
                s = SNPs("tests/input/generic.csv", output_dir=tmpdir1)

                # setup resource to use test FASTA reference sequence
                r = Resources()
                r._reference_sequences["GRCh37"] = {}

                output = os.path.join(tmpdir1, "generic_GRCh37.vcf")
                with tempfile.TemporaryDirectory() as tmpdir2:
                    dest = os.path.join(tmpdir2, "generic.fa.gz")
                    gzip_file("tests/input/generic.fa", dest)

                    seq = ReferenceSequence(ID="1", path=dest)

                    r._reference_sequences["GRCh37"]["1"] = seq

                    # save phased data to VCF
                    self.assertEqual(
                        s.to_vcf(
                            qc_only=vcf_qc_only,
                            qc_filter=vcf_qc_filter,
                        ),
                        output,
                    )

                    # read result
                    with open(output, "r") as f:
                        actual = f.read()

                    # read expected result
                    with open(expected_output, "r") as f:
                        expected = f.read()

                    self.assertIn(expected, actual)

                    if not vcf_qc_filter or not cluster:
                        self.assertNotIn("##FILTER=<ID=lq", actual)

        self.run_low_quality_snps_test(f, self.get_low_quality_snps(), cluster=cluster)

    def run_vcf_indel_test(
        self, input_data, expected_output, output_includes_ins, output_includes_del
    ):
        with tempfile.TemporaryDirectory() as tmpdir1:
            s = SNPs(input_data.encode(), output_dir=tmpdir1)

            r = Resources()
            r._reference_sequences["GRCh37"] = {}

            output = os.path.join(tmpdir1, "generic_GRCh37.vcf")
            with tempfile.TemporaryDirectory() as tmpdir2:
                dest = os.path.join(tmpdir2, "generic.fa.gz")
                gzip_file("tests/input/generic.fa", dest)

                seq = ReferenceSequence(ID="1", path=dest)

                r._reference_sequences["GRCh37"]["1"] = seq

                self.assertEqual(s.to_vcf(), output)

                with open(output, "r") as f:
                    actual = f.read()

                # Check if expected output is included
                self.assertIn(expected_output, actual)

                # Check for ALT headers
                if output_includes_ins:
                    self.assertIn("##ALT=<ID=INS", actual)
                else:
                    self.assertNotIn("##ALT=<ID=INS", actual)

                if output_includes_del:
                    self.assertIn("##ALT=<ID=DEL", actual)
                else:
                    self.assertNotIn("##ALT=<ID=DEL", actual)

    def test_save_vcf_qc_only_F_qc_filter_F(self):
        self.run_vcf_qc_test(
            "tests/output/vcf_qc/qc_only_F_qc_filter_F.vcf",
            vcf_qc_only=False,
            vcf_qc_filter=False,
        )

    def test_save_vcf_qc_only_F_qc_filter_T(self):
        self.run_vcf_qc_test(
            "tests/output/vcf_qc/qc_only_F_qc_filter_T.vcf",
            vcf_qc_only=False,
            vcf_qc_filter=True,
        )

    def test_save_vcf_qc_only_T_qc_filter_F(self):
        self.run_vcf_qc_test(
            "tests/output/vcf_qc/qc_only_T_qc_filter_F.vcf",
            vcf_qc_only=True,
            vcf_qc_filter=False,
        )

    def test_save_vcf_qc_only_T_qc_filter_T(self):
        self.run_vcf_qc_test(
            "tests/output/vcf_qc/qc_only_T_qc_filter_T.vcf",
            vcf_qc_only=True,
            vcf_qc_filter=True,
        )

    def test_save_vcf_no_cluster(self):
        self.run_vcf_qc_test(
            "tests/output/vcf_qc/qc_only_F_qc_filter_F.vcf",
            vcf_qc_only=False,
            vcf_qc_filter=False,
            cluster="",
        )
        self.run_vcf_qc_test(
            "tests/output/vcf_qc/qc_only_F_qc_filter_F.vcf",
            vcf_qc_only=False,
            vcf_qc_filter=True,
            cluster="",
        )
        self.run_vcf_qc_test(
            "tests/output/vcf_qc/qc_only_F_qc_filter_F.vcf",
            vcf_qc_only=True,
            vcf_qc_filter=False,
            cluster="",
        )
        self.run_vcf_qc_test(
            "tests/output/vcf_qc/qc_only_F_qc_filter_F.vcf",
            vcf_qc_only=True,
            vcf_qc_filter=True,
            cluster="",
        )

    def test_save_vcf_indels(self):
        test_cases = [
            {
                "input": """rsid,chromosome,position,genotype
rs1,1,101,II
""",
                "expected_output": """##ALT=<ID=INS,Description="Insertion of novel sequence relative to the reference">
##INFO=<ID=SVTYPE,Number=.,Type=String,Description="Type of structural variant: INS (Insertion), DEL (Deletion)">
##INFO=<ID=IMPRECISE,Number=0,Type=Flag,Description="Imprecise structural variation">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE
1\t101\trs1\tA\t<INS>\t.\t.\tSVTYPE=INS;IMPRECISE\tGT\t1/1
""",
                "output_includes_ins": True,
                "output_includes_del": False,
            },
            {
                "input": """rsid,chromosome,position,genotype
rs1,1,101,DD
""",
                "expected_output": """##ALT=<ID=DEL,Description="Deletion relative to the reference">
##INFO=<ID=SVTYPE,Number=.,Type=String,Description="Type of structural variant: INS (Insertion), DEL (Deletion)">
##INFO=<ID=IMPRECISE,Number=0,Type=Flag,Description="Imprecise structural variation">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE
1\t101\trs1\tA\t<DEL>\t.\t.\tSVTYPE=DEL;IMPRECISE\tGT\t1/1
""",
                "output_includes_ins": False,
                "output_includes_del": True,
            },
            {
                "input": """rsid,chromosome,position,genotype
rs1,1,101,ID
""",
                "expected_output": """##ALT=<ID=DEL,Description="Deletion relative to the reference">
##ALT=<ID=INS,Description="Insertion of novel sequence relative to the reference">
##INFO=<ID=SVTYPE,Number=.,Type=String,Description="Type of structural variant: INS (Insertion), DEL (Deletion)">
##INFO=<ID=IMPRECISE,Number=0,Type=Flag,Description="Imprecise structural variation">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE
1\t101\trs1\tA\t<DEL>,<INS>\t.\t.\tSVTYPE=DEL,INS;IMPRECISE\tGT\t2/1
""",
                "output_includes_ins": True,
                "output_includes_del": True,
            },
            {
                "input": """rsid,chromosome,position,genotype
rs1,1,101,DI
""",
                "expected_output": """##ALT=<ID=DEL,Description="Deletion relative to the reference">
##ALT=<ID=INS,Description="Insertion of novel sequence relative to the reference">
##INFO=<ID=SVTYPE,Number=.,Type=String,Description="Type of structural variant: INS (Insertion), DEL (Deletion)">
##INFO=<ID=IMPRECISE,Number=0,Type=Flag,Description="Imprecise structural variation">
##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE
1\t101\trs1\tA\t<DEL>,<INS>\t.\t.\tSVTYPE=DEL,INS;IMPRECISE\tGT\t1/2
""",
                "output_includes_ins": True,
                "output_includes_del": True,
            },
        ]

        for case in test_cases:
            with self.subTest(case=case):
                self.run_vcf_indel_test(
                    case["input"],
                    case["expected_output"],
                    case["output_includes_ins"],
                    case["output_includes_del"],
                )
