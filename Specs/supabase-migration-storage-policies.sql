-- Supabase Storage policies (run after buckets exist in dashboard).
-- booking-documents must stay private; item-images may be public read.

-- booking-documents: no anonymous access
DROP POLICY IF EXISTS booking_documents_deny_anon_select ON storage.objects;
CREATE POLICY booking_documents_deny_anon_select
  ON storage.objects
  FOR SELECT
  TO anon
  USING (bucket_id = 'booking-documents' AND false);

DROP POLICY IF EXISTS booking_documents_deny_anon_insert ON storage.objects;
CREATE POLICY booking_documents_deny_anon_insert
  ON storage.objects
  FOR INSERT
  TO anon
  WITH CHECK (bucket_id = 'booking-documents' AND false);

-- booking-documents: no authenticated-user access (API service role only)
DROP POLICY IF EXISTS booking_documents_deny_authenticated_select ON storage.objects;
CREATE POLICY booking_documents_deny_authenticated_select
  ON storage.objects
  FOR SELECT
  TO authenticated
  USING (bucket_id = 'booking-documents' AND false);

DROP POLICY IF EXISTS booking_documents_deny_authenticated_insert ON storage.objects;
CREATE POLICY booking_documents_deny_authenticated_insert
  ON storage.objects
  FOR INSERT
  TO authenticated
  WITH CHECK (bucket_id = 'booking-documents' AND false);

DROP POLICY IF EXISTS booking_documents_deny_authenticated_update ON storage.objects;
CREATE POLICY booking_documents_deny_authenticated_update
  ON storage.objects
  FOR UPDATE
  TO authenticated
  USING (bucket_id = 'booking-documents' AND false);

DROP POLICY IF EXISTS booking_documents_deny_authenticated_delete ON storage.objects;
CREATE POLICY booking_documents_deny_authenticated_delete
  ON storage.objects
  FOR DELETE
  TO authenticated
  USING (bucket_id = 'booking-documents' AND false);

-- item-images: public read (catalog photos)
DROP POLICY IF EXISTS item_images_public_read ON storage.objects;
CREATE POLICY item_images_public_read
  ON storage.objects
  FOR SELECT
  TO anon, authenticated
  USING (bucket_id = 'item-images');

NOTIFY pgrst, 'reload schema';
