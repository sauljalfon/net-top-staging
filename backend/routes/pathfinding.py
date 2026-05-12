from fastapi import APIRouter, HTTPException, Query

from src.pathfinding import (
    find_path_from_device_to_agg,
    find_all_paths_from_agg,
    find_full_bidirectional_paths,
    find_all_paths_from_entity,
    find_path_between_ports,
)

router = APIRouter()

@router.get("/device/{device_id}/to-agg")
def get_path_to_agg(device_id: int):
    try:
        result = find_path_from_device_to_agg(device_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/agg/{agg_id}/downstream")
def get_downstream_paths(agg_id: int, max_paths: int = Query(100)):
    try:
        result = find_all_paths_from_agg(agg_id, max_paths=max_paths)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/agg/{agg_id}/full")
def get_full_bidirectional(agg_id: int, max_paths: int = Query(100)):
    try:
        result = find_full_bidirectional_paths(agg_id, max_paths=max_paths)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/device/{device_id}/info")
def get_device_connectivity_info(device_id: int):
    try:
        path_result = find_path_from_device_to_agg(device_id)
        return {
            'device_id': device_id,
            'device_name': path_result['start_device']['name'] if path_result.get('start_device') else None,
            'device_type': path_result['start_device']['type'] if path_result.get('start_device') else None,
            'is_connected_to_agg': path_result['reached_agg'],
            'hop_count_to_agg': path_result['total_hops'],
            'agg_device': path_result['agg_device'],
            'path': path_result['path']
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/trace")
def trace_entity_paths(
    entity_type: str = Query(..., description="Type of entity ('device', 'panel', or 'port')"),
    entity_id: int = Query(..., description="ID of the entity"),
    max_paths: int = Query(100),
    max_depth: int = Query(50)
):
    try:
        result = find_all_paths_from_entity(entity_type, entity_id, max_paths, max_depth)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/between")
def calculate_path_between_ports(
    port_a_id: int = Query(..., description="Source port ID"),
    port_b_id: int = Query(..., description="Destination port ID"),
    max_depth: int = Query(50, description="Maximum hops to search")
):
    try:
        result = find_path_between_ports(port_a_id, port_b_id, max_depth)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")