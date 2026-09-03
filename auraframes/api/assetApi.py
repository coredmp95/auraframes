from auraframes.api.baseApi import BaseApi
from auraframes.client import WriteEndpointError

# TODO: Untested
from auraframes.models.asset import Asset, AssetPartial, AssetPartialId


class AssetApi(BaseApi):

    def batch_update(self, assets: Asset | AssetPartial | list[Asset | AssetPartial]) -> tuple[list[str], list[AssetPartialId]]:
        """
        Posts new metadata to the API for one or more assets. This does not appear to affect the
        frame; however subsequent calls to retrieve the asset(s) will have the modified metadata.

        Primarily used to update an asset after the image has been uploaded to S3.

        This is a native Pushd BATCH endpoint: the official app sends the whole collection of
        assets to update in a single `{"assets": [...]}` call rather than one call per asset. A
        single `Asset`/`AssetPartial` is accepted for backward compatibility (normalized to a
        one-element list); the legacy single-item caller (`Aura.upload_image`) discards this
        method's return value, so this does not change its behavior.

        `successes` in the response (each carrying `id` + `local_identifier`) is the per-file
        source of truth for batch callers: match each sent item's `local_identifier` against
        `successes[].local_identifier` to attribute success/failure per item -- a partial
        `successes` list (fewer entries than sent) is the NORMAL, expected signal in batch mode
        that the caller must attribute per-item, not an error to raise on. Only the `error`
        envelope (a whole-call failure) raises here.

        :param assets: A single `Asset`/`AssetPartial`, or a list of them, to update in one call.
        :return: List of sent remote ids, list of received AssetPartialId successes (may be a
            partial subset of what was sent -- see above).
        """
        items = assets if isinstance(assets, list) else [assets]

        json_response = self._client.put(f'/assets/batch_update.json', data={
            "assets": [
                item.dict(
                    include={
                        'data_uti': True,
                        'favorite': True,
                        'file_name': True,
                        'height': True,
                        'local_identifier': True,
                        'location': True,
                        'md5_hash': True,
                        'modified_at': True,
                        'orientation': True,
                        'selected': True,
                        'taken_at': True,
                        'upload_priority': True,
                        'width': True
                    })
                for item in items
            ]
        })
        if json_response.get('error'):
            raise WriteEndpointError(f"batch_update failed: {json_response.get('error')}")

        ids = json_response.get('ids') or []
        successes = json_response.get('successes') or []

        return ids, [AssetPartialId(**partial_asset_id) for partial_asset_id in successes]

    def get_asset_by_local_identifier(self, local_id: str):
        """
        Retrieves an asset given a local id.
        :param local_id: A local id string.
        :return: The retrieved asset, related child albums, and any smart adds related to the asset.
        """
        json_response = self._client.get(f'/assets/asset_for_local_identifier.json',
                                         query_params={'local_identifier': local_id})

        return Asset(**json_response.get('asset')), json_response.get('child_albums'), json_response.get('smart_adds')

    def update_taken_at_date(self, asset: Asset) -> Asset:
        """
        Updates an asset's taken_date and taken_at_granularity. This will modify the date displayed in the frame and
        from future responses.
        :param asset: Asset with new taken_at or taken_at_granularity
        :return: The asset with modified dates
        """
        # Asset.id is a required str (never None for a server-hydrated
        # Asset), so this always uses the id-based request shape.
        request = {
            'taken_at': asset.taken_at,
            'taken_at_granularity': asset.taken_at_granularity,
            'id': asset.id,
        }

        json_response = self._client.post(f'/assets/update_taken_at_date.json', data=request)
        return Asset(**json_response)

    def delete_asset(self, asset: Asset):
        """
        Deletes the asset. **Currently unknown if this is used, most deletions occur by removing
        the activity; maybe this deletes it from S3/Glacier** see :func:`FrameApi.remove_asset`

        :param asset: Asset for removal
        :return: TODO
        """
        # Asset.id is a required str (never None for a server-hydrated
        # Asset), so this always uses the id-based delete endpoint.
        json_response = self._client.delete(f'/assets/{asset.id}.json')

        if json_response.get('error'):
            raise WriteEndpointError(f"delete_asset failed: {json_response.get('error')}")

        return json_response

    def crop_asset(self, asset: Asset) -> Asset:
        """
        Crops an asset, modifying `rotation_cw`, `user_landscape_rect`, `user_portrait_rect` and related
        aspect ratio rects.
        :param asset: Asset containing new rotation/rect data.
        :return: The asset with modified crop fields.
        """
        json_response = self._client.post(f'/assets/crop.json', data=asset.dict(
            include={
                'id': True,
                'local_identifier': True,
                'user_id': True,
                'rotation_cw': True,
                'user_landscape_16_10_rect': True,
                'user_landscape_rect': True,
                'user_portrait_4_5_rect': True,
                'user_portrait_rect': True
            }))

        return Asset(**json_response.get('asset'))
