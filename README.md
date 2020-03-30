### slcp2cod
This repository contains jobs to convert S1-SLCP products to Coherenece Differences (CODs) for creating Damage Proxy Maps v1 (DPMv1).

A COD is created based on the below pairing system, using 3 SLCs --> 2 SLCPs --> 1 COD:
![image](https://user-images.githubusercontent.com/6346909/77940914-e62cf680-72a8-11ea-96a0-62430700a7cb.png)

Associated job:
### Job 1: S1 COD - Network Selection
This job does network selection / pairing of pre-event SLCPs with the co-event SLCP in the specified AOI to submit to the [S1 COD](#Job-2--S1-COD) job (Job 2 below) to create CODs
- Type: **Individual**
- Facet: **Not needed**
- User inputs:

    | Fields        | Description   | Type  |Example  |
    | ------------- |-------------| :---------:| :---------:|
    | `dataset_tag`     | Suffix dataset tag to append at the end of the dataset id for differentiating events or settings  | string | `'standard'`  |
    | `project`      | Project category for possible queue propagation later   |  enum | `'ariamh'`  |
    | `slcp_version`      | SLCP version to pair CODs for. Default is `v1.2`  |  string | `'v1.2'`  |
    | `aoi_name`      | Dataset ID of AOI to find SLCPs for CODs creation based on AOI's coordinates, start, end and event time.  |  string | `'AOI_Japan_Earthquake'`  |
    | `track_number`      | (Optional) Specific track number (only one allowed) of SLCPs overlapping AOI to process CODs for. If not specified, creates CODs for all tracks overlapping AOI.  |  int | `171`  |
    | `overriding_range_looks` | (Optional) Range looks to override SLCP's range looks to create CODs in the format: subswath1, subswath2, subswath3. If not specified, uses the range looks stored in SLCP for _all subswaths_.  |  int,int,int | `16,16,16`  |
    | `overriding_azimuth_looks` | (Optional) Azimuth looks to override SLCP's azimuth looks to create CODs in the format: subswath1, subswath2, subswath3. If not specified, uses the azimuth looks stored in SLCP for _all subswaths_.  |  int,int,int | `4,4,4`  |
    | `min_match`      |  Minimum number of CODs to created. Priority of creation is based on temporal baseline. (See Notes below) |  int | `1`  |
    | `min_overlap`      | Minimum ratio of overlap between pre-event_SLCP and co-event_SLCP. Should be < 1. (See Notes below)  |  float | `0.7`  |

- Important outputs:
    - No products will be directly generated, only [S1-COD](#Job-2--S1-COD) jobs will be submitted based on pairing results. (Expect 1 job for each subswath)
    
 - Notes:
    * The COD network selector pairs SLCPs to submit to the `S1-COD` job based on the following workflow:
        1. Gather `pre-event_SLCPs` + `co-event_SLCPs` from GRQ. Search criteria:
            1. SLCPs are pre-event if `SLCP_end_time < AOI_event_time`
            1. SLCPs are co-event if `SLCP_start_time < AOI_event_time < SLCP_end_time ` 
        
        2. Match pre-event_SLCP and co-event_SLCP pairs if:
            1. `pre-event_SLCP[‘master_time’] - co-event_SLCP[‘master_time’] < 1 day`
            1. `area_intersect(pre-event_SLCP,co-event_SLCP) / area(co-event_SLCP) > min_overlap`
      
        3. Creates and returns `minmatch` or valid SLCP pairs for COD based on shortest temporal baseline, where
            * temporal baseline = `co-event_SLC['slave_time'] -  pre-event_SLCP['slave_time']`
        
    Hence, if there are multiple pre-event SLCPs as per the following:
    ![image](https://user-images.githubusercontent.com/6346909/77940839-cbf31880-72a8-11ea-95e2-56e49e30cee2.png)
    
    
    * If `minmatch` = 1, only COD 1's job will be submitted 
    * If `minmatch` = 2, both COD 2 and COD 1 will be submitted

### Job 2: S1 COD 
- Type: **Individual**
- Facet: **Not needed**
- User inputs:

    | Fields        | Description   | Type  |Example  |
    | ------------- |-------------| :---------:| :---------:|
    | `dataset_tag`     | Suffix dataset tag to append at the end of the dataset id for differentiating events or settings  | string | `'standard'`  |
    | `project`      | Project category for possible queue propagation later   |  enum | `'ariamh'`  |
    | `url1`      | Pre-event SLCP dataset's *s3* url  |  string | s3://s3-\<region\>.amazonaws.com:80/ <br> <bucket_name>/datasets/slc_pair/v1.2/ <br> \<year\>/\<month\>/\<day\>/<S1-SLCP_ID>  |
    | `url2`      | Co-event SLCP dataset's *s3* url  |  string | s3://s3-\<region\>.amazonaws.com:80/ <br> <bucket_name>/datasets/slc_pair/v1.2/ <br> \<year\>/\<month\>/\<day\>/<S1-SLCP_ID>  |
    | `overriding_range_looks` | (Optional) Range looks to override SLCP's range looks to create CODs for that specific SLCP subswath.|  int | `16`  |
    | `overriding_azimuth_looks` | (Optional) Azimuth looks to override SLCP's azimuth looks to create CODs for that specific SLCP subswath.|  int | `4`  |

- Important outputs:

    | Product        | Description   | Example  |
    | ------------- |-------------| :-----|
    | Coherence Difference  | Geocoded, multilooked CODs. <br> Band 1 - Pre-event SLCP's Amplitude. <br> Band 2 - Coherence Difference (pre-event - co-event).  | 	diff_cor_[burst]\_[range_lks]\_[az_lks].cor.geo|
    | Pre-event SLCP Coherence  | 2-Band geocoded, multilooked  coherence (COR) of **pre-event** SLCP. <br> Band 1 - Amplitude. <br> Band 2 - Coherence. | cor_[burst]\_[range_lks]\_[az_lks].cor.geo|
    | Co-event SLCP Coherence  | 2-Band geocoded, multilooked  coherence (COR) of **co-event** SLCP.  <br> Band 1 - Amplitude. <br> Band 2 - Coherence. | cor2_[burst]\_[range_lks]\_[az_lks].cor.geo|

- Notes:
    * The CODs in this PGE are computed as such (from `burst_coherence_diff.py`):
    
        ![formula](https://render.githubusercontent.com/render/math?math=COD=COR_{preeventslcp}-COR_{coeventslcp})
        
        where _COR_ = Coherence of given co-registered SLCP
        
        => Positve values correspond to decreased coherence after event and possible damage due to event.
