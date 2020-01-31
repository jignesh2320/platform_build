#
# Copyright (C) 2019 The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import os
import os.path
import zipfile

import apex_utils
import common
import test_utils


class ApexUtilsTest(test_utils.ReleaseToolsTestCase):

  # echo "foo" | sha256sum
  SALT = 'b5bb9d8014a0f9b1d61e21e796d78dccdf1352f23cd32812f4850b878ae4944c'

  def setUp(self):
    self.testdata_dir = test_utils.get_testdata_dir()
    # The default payload signing key.
    self.payload_key = os.path.join(self.testdata_dir, 'testkey.key')

    common.OPTIONS.search_path = test_utils.get_search_path()

  @staticmethod
  def _GetTestPayload():
    payload_file = common.MakeTempFile(prefix='apex-', suffix='.img')
    with open(payload_file, 'wb') as payload_fp:
      payload_fp.write(os.urandom(8192))
    return payload_file

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_ParseApexPayloadInfo(self):
    payload_file = self._GetTestPayload()
    apex_utils.SignApexPayload(
        'avbtool', payload_file, self.payload_key, 'testkey', 'SHA256_RSA2048',
        self.SALT, no_hashtree=True)
    payload_info = apex_utils.ParseApexPayloadInfo('avbtool', payload_file)
    self.assertEqual('SHA256_RSA2048', payload_info['Algorithm'])
    self.assertEqual(self.SALT, payload_info['Salt'])
    self.assertEqual('testkey', payload_info['apex.key'])
    self.assertEqual('0 bytes', payload_info['Tree Size'])

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_SignApexPayload(self):
    payload_file = self._GetTestPayload()
    apex_utils.SignApexPayload(
        'avbtool', payload_file, self.payload_key, 'testkey', 'SHA256_RSA2048',
        self.SALT, no_hashtree=True)
    apex_utils.VerifyApexPayload(
        'avbtool', payload_file, self.payload_key, True)

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_SignApexPayload_withHashtree(self):
    payload_file = self._GetTestPayload()
    apex_utils.SignApexPayload(
        'avbtool', payload_file, self.payload_key, 'testkey', 'SHA256_RSA2048',
        self.SALT, no_hashtree=False)
    apex_utils.VerifyApexPayload('avbtool', payload_file, self.payload_key)
    payload_info = apex_utils.ParseApexPayloadInfo('avbtool', payload_file)
    self.assertEqual('4096 bytes', payload_info['Tree Size'])

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_SignApexPayload_noHashtree(self):
    payload_file = self._GetTestPayload()
    apex_utils.SignApexPayload(
        'avbtool', payload_file, self.payload_key, 'testkey', 'SHA256_RSA2048',
        self.SALT, no_hashtree=True)
    apex_utils.VerifyApexPayload('avbtool', payload_file, self.payload_key,
                                 no_hashtree=True)
    payload_info = apex_utils.ParseApexPayloadInfo('avbtool', payload_file)
    self.assertEqual('0 bytes', payload_info['Tree Size'])

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_SignApexPayload_withSignerHelper(self):
    payload_file = self._GetTestPayload()
    signing_helper = os.path.join(self.testdata_dir, 'signing_helper.sh')
    os.chmod(signing_helper, 0o700)
    payload_signer_args = '--signing_helper_with_files {}'.format(
        signing_helper)
    apex_utils.SignApexPayload(
        'avbtool',
        payload_file,
        self.payload_key,
        'testkey', 'SHA256_RSA2048', self.SALT,
        True,
        payload_signer_args)
    apex_utils.VerifyApexPayload(
        'avbtool', payload_file, self.payload_key, True)

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_SignApexPayload_invalidKey(self):
    self.assertRaises(
        apex_utils.ApexSigningError,
        apex_utils.SignApexPayload,
        'avbtool',
        self._GetTestPayload(),
        os.path.join(self.testdata_dir, 'testkey.x509.pem'),
        'testkey',
        'SHA256_RSA2048',
        self.SALT,
        no_hashtree=True)

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_VerifyApexPayload_wrongKey(self):
    payload_file = self._GetTestPayload()
    apex_utils.SignApexPayload(
        'avbtool', payload_file, self.payload_key, 'testkey', 'SHA256_RSA2048',
        self.SALT, True)
    apex_utils.VerifyApexPayload(
        'avbtool', payload_file, self.payload_key, True)
    self.assertRaises(
        apex_utils.ApexSigningError,
        apex_utils.VerifyApexPayload,
        'avbtool',
        payload_file,
        os.path.join(self.testdata_dir, 'testkey_with_passwd.key'),
        no_hashtree=True)

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_ApexApkSigner_noApkPresent(self):
    apex_path = os.path.join(self.testdata_dir, 'foo.apex')
    signer = apex_utils.ApexApkSigner(apex_path, None, None)
    processed_apex = signer.ProcessApexFile({}, self.payload_key,
                                            None)
    self.assertEqual(apex_path, processed_apex)

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_ApexApkSigner_apkKeyNotPresent(self):
    apex_path = os.path.join(self.testdata_dir, 'has_apk.apex')
    signer = apex_utils.ApexApkSigner(apex_path, None, None)
    self.assertRaises(apex_utils.ApexSigningError, signer.ProcessApexFile, {},
                      self.payload_key, None)

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_ApexApkSigner_signApk(self):
    apex_path = os.path.join(self.testdata_dir, 'has_apk.apex')
    signer = apex_utils.ApexApkSigner(apex_path, None, None)
    apk_keys = {'wifi-service-resources.apk': os.path.join(
        self.testdata_dir, 'testkey')}

    self.payload_key = os.path.join(self.testdata_dir, 'testkey_RSA4096.key')
    payload_pubkey = common.ExtractAvbPublicKey('avbtool',
                                                self.payload_key)
    signer.ProcessApexFile(apk_keys, self.payload_key, payload_pubkey)

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_ApexApkSigner_noAssetDir(self):
    apex_path = os.path.join(self.testdata_dir, 'has_apk.apex')
    no_asset = common.MakeTempFile(suffix='.apex')
    with zipfile.ZipFile(no_asset, 'w') as output_zip:
      with zipfile.ZipFile(apex_path, 'r') as input_zip:
        name_list = input_zip.namelist()
        for name in name_list:
          if not name.startswith('assets'):
            output_zip.writestr(name, input_zip.read(name))

    signer = apex_utils.ApexApkSigner(no_asset, None, None)
    apk_keys = {'wifi-service-resources.apk': os.path.join(
        self.testdata_dir, 'testkey')}

    self.payload_key = os.path.join(self.testdata_dir, 'testkey_RSA4096.key')
    payload_pubkey = common.ExtractAvbPublicKey('avbtool',
                                                self.payload_key)
    signer.ProcessApexFile(apk_keys, self.payload_key, payload_pubkey)

  @test_utils.SkipIfExternalToolsUnavailable()
  def test_ApexApkSigner_withSignerHelper(self):
    apex_path = os.path.join(self.testdata_dir, 'has_apk.apex')
    signer = apex_utils.ApexApkSigner(apex_path, None, None)
    apk_keys = {'wifi-service-resources.apk': os.path.join(
        self.testdata_dir, 'testkey')}

    self.payload_key = os.path.join(self.testdata_dir, 'testkey_RSA4096.key')
    payload_pubkey = common.ExtractAvbPublicKey('avbtool', self.payload_key)

    signing_helper = os.path.join(self.testdata_dir, 'signing_helper.sh')
    os.chmod(signing_helper, 0o700)
    payload_signer_args = '--signing_helper_with_files={}'.format(
        signing_helper)
    signer.ProcessApexFile(apk_keys, self.payload_key, payload_pubkey,
                           payload_signer_args)
